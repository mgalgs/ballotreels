"""The SQLite-backed store behind the serve tier: the cache of finished
videos, and the job queue the worker API and queue monitor work against.

One connection per process, guarded by a lock for our own compound
read-modify-write operations (SQLite serializes writers on its own, but
"join a live job or create one" needs to be atomic across more than one
statement, and so does claiming the oldest queued job). WAL mode so the
queue survives a restart without losing anything committed.

A job's `claim` is a token handed to whichever worker holds it; every
worker request after claiming must present it, and a mismatch (the job
was requeued or cancelled out from under that worker) is reported as a
409 rather than silently accepted.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .index import key_string

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    key_hash TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    election TEXT NOT NULL,
    division TEXT NOT NULL,
    contest TEXT NOT NULL,
    standard_version INTEGER NOT NULL,
    template_version INTEGER NOT NULL,
    storage TEXT NOT NULL,
    urls TEXT NOT NULL,
    sources TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    election TEXT NOT NULL,
    division TEXT NOT NULL,
    contest TEXT NOT NULL,
    standard_version INTEGER NOT NULL,
    template_version INTEGER NOT NULL,
    state TEXT NOT NULL,
    stage TEXT,
    queued_at REAL NOT NULL,
    claim TEXT,
    worker_id TEXT,
    last_heartbeat REAL,
    started_at REAL,
    finished_at REAL,
    duration REAL,
    error TEXT,
    failed_stage TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS jobs_live_key
    ON jobs(key) WHERE state IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS stage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    event TEXT NOT NULL,
    at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    last_seen REAL NOT NULL
);
"""

# Which states an admin action may start from (docs in the brief, A13).
TRANSITIONS = {
    "retry": {"failed", "cancelled"},
    "cancel": {"queued", "running"},
    "requeue": {"running"},
}


def hash_for_key(key: tuple[str, str, str, int, int]) -> str:
    """The 16-hex-char cache directory / URL name for a cache key
    (docs/ARCHITECTURE.md): a hash, not the key itself, so an OCD-ID's
    slashes and colons never end up in a path or URL."""
    return hashlib.sha256(key_string(key).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Video:
    key_hash: str
    key: str
    storage: str
    urls: dict[str, str]
    sources: list[dict[str, Any]]
    created_at: float


class JobQueue:
    def __init__(self, path: str | Path,
                clock: Callable[[], float] = time.time,
                heartbeat_timeout: float = 120.0):
        self.clock = clock
        self.heartbeat_timeout = heartbeat_timeout
        # Called (job_id, claim) outside the lock whenever a running job
        # stops being running without finishing, so the server can drop
        # that job's `.incoming/` upload directory.
        self.on_vacate: Callable[[int, str], None] | None = None
        self._lock = threading.Lock()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- videos ------------------------------------------------------

    def record_video(self, key: tuple[str, str, str, int, int], storage: str,
                     urls: dict[str, str],
                     sources: list[dict[str, Any]]) -> None:
        with self._lock:
            self._insert_video_locked(key, storage, urls, sources)
            self._conn.commit()

    def _insert_video_locked(self, key: tuple[str, str, str, int, int],
                             storage: str, urls: dict[str, str],
                             sources: list[dict[str, Any]]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO videos "
            "(key_hash, key, election, division, contest, "
            "standard_version, template_version, storage, urls, "
            "sources, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (hash_for_key(key), key_string(key), *key, storage,
             json.dumps(urls), json.dumps(sources), self.clock()))

    def video_for(self, key: tuple[str, str, str, int, int]) -> Video | None:
        return self.video_for_hash(hash_for_key(key))

    def video_for_hash(self, key_hash: str) -> Video | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT key_hash, key, storage, urls, sources, created_at "
                "FROM videos WHERE key_hash = ?", (key_hash,)).fetchone()
        if row is None:
            return None
        return Video(key_hash=row["key_hash"], key=row["key"],
                    storage=row["storage"], urls=json.loads(row["urls"]),
                    sources=json.loads(row["sources"]),
                    created_at=row["created_at"])

    def known_hashes(self) -> set[str]:
        with self._lock:
            rows = self._conn.execute("SELECT key_hash FROM videos").fetchall()
        return {r["key_hash"] for r in rows}

    # -- jobs: creation and lookup ------------------------------------

    def find_live_job(self, key: tuple[str, str, str, int, int]
                      ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE key = ? AND state IN "
                "('queued', 'running')", (key_string(key),)).fetchone()
        return dict(row) if row is not None else None

    def create_job(self, key: tuple[str, str, str, int, int]
                   ) -> tuple[dict[str, Any], bool]:
        """Returns (job, created): created is False if another live job
        for this key won the race (the unique index catches it)."""
        now = self.clock()
        with self._lock:
            try:
                cur = self._conn.execute(
                    "INSERT INTO jobs (key, key_hash, election, division, "
                    "contest, standard_version, template_version, state, "
                    "stage, queued_at) VALUES (?, ?, ?, ?, ?, ?, ?, "
                    "'queued', NULL, ?)",
                    (key_string(key), hash_for_key(key), *key, now))
                self._conn.commit()
                job_id = cur.lastrowid
            except sqlite3.IntegrityError:
                self._conn.rollback()
                row = self._conn.execute(
                    "SELECT * FROM jobs WHERE key = ? AND state IN "
                    "('queued', 'running')", (key_string(key),)).fetchone()
                return dict(row), False
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row), True

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock:
            self._sweep_stale_locked(self.clock())
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row is not None else None

    def position_of(self, job_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT queued_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return 0
            queued_at = row["queued_at"]
            count = self._conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE state = 'queued' AND "
                "(queued_at < ? OR (queued_at = ? AND id < ?))",
                (queued_at, queued_at, job_id)).fetchone()[0]
        return count + 1

    def median_seconds(self) -> float | None:
        with self._lock:
            rows = self._conn.execute(
                "SELECT duration FROM jobs WHERE state = 'done' AND "
                "duration IS NOT NULL ORDER BY finished_at DESC "
                "LIMIT 20").fetchall()
        durations = sorted(r["duration"] for r in rows)
        if not durations:
            return None
        n = len(durations)
        mid = n // 2
        if n % 2:
            return durations[mid]
        return (durations[mid - 1] + durations[mid]) / 2

    def eta_minutes(self, job: dict[str, Any],
                    default_minutes: float = 10.0) -> int:
        median = self.median_seconds()
        seconds = median if median is not None else default_minutes * 60
        if job["state"] == "queued":
            minutes = self.position_of(job["id"]) * seconds / 60
        elif job["state"] == "running":
            elapsed = self.clock() - (job["started_at"] or self.clock())
            minutes = (seconds - elapsed) / 60
        else:
            return 0
        return max(1, round(minutes))

    # -- worker API ----------------------------------------------------

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        now = self.clock()
        with self._lock:
            self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE state = 'queued' "
                "ORDER BY queued_at, id LIMIT 1").fetchone()
            if row is None:
                return None
            claim_token = secrets.token_hex(16)
            self._conn.execute(
                "UPDATE jobs SET state = 'running', claim = ?, "
                "worker_id = ?, last_heartbeat = ?, started_at = ? "
                "WHERE id = ?", (claim_token, worker_id, now, now, row["id"]))
            self._conn.execute(
                "INSERT OR REPLACE INTO workers (id, last_seen) "
                "VALUES (?, ?)", (worker_id, now))
            self._conn.commit()
            job = dict(self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone())
        return job

    def heartbeat(self, job_id: int, claim: str, stage: str | None) -> bool:
        now = self.clock()
        with self._lock:
            vacated = self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            ok = (row is not None and row["claim"] == claim
                 and row["state"] == "running")
            if ok:
                self._conn.execute(
                    "UPDATE jobs SET last_heartbeat = ?, stage = ? "
                    "WHERE id = ?", (now, stage, job_id))
                self._conn.execute(
                    "INSERT OR REPLACE INTO workers (id, last_seen) "
                    "VALUES (?, ?)", (row["worker_id"], now))
                self._conn.commit()
        self._notify_vacated(vacated)
        return ok

    def stage_event(self, job_id: int, claim: str, stage: str,
                    event: str) -> bool:
        now = self.clock()
        with self._lock:
            vacated = self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            ok = (row is not None and row["claim"] == claim
                 and row["state"] == "running")
            if ok:
                self._conn.execute(
                    "UPDATE jobs SET stage = ?, last_heartbeat = ? "
                    "WHERE id = ?", (stage, now, job_id))
                self._conn.execute(
                    "INSERT INTO stage_events (job_id, stage, event, at) "
                    "VALUES (?, ?, ?, ?)", (job_id, stage, event, now))
                self._conn.commit()
        self._notify_vacated(vacated)
        return ok

    def fail(self, job_id: int, claim: str, stage: str, output: str) -> bool:
        now = self.clock()
        with self._lock:
            vacated = self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            ok = (row is not None and row["claim"] == claim
                 and row["state"] == "running")
            if ok:
                self._conn.execute(
                    "UPDATE jobs SET state = 'failed', stage = ?, "
                    "failed_stage = ?, error = ?, finished_at = ? "
                    "WHERE id = ?", (stage, stage, output, now, job_id))
                self._conn.execute(
                    "INSERT INTO stage_events (job_id, stage, event, at) "
                    "VALUES (?, ?, 'fail', ?)", (job_id, stage, now))
                self._conn.commit()
        self._notify_vacated(vacated)
        if ok:
            self._vacate_one(job_id, claim)
        return ok

    def complete(self, job_id: int, claim: str,
                 video: tuple[tuple[str, str, str, int, int], str,
                              dict[str, str], list[dict[str, Any]]]
                 | None = None) -> bool:
        """Mark a running job done. With `video` (key, storage, urls,
        sources), its `videos` row is written in the same transaction,
        so a cancel, requeue or timeout sweep that wins the race leaves
        no video recorded for a job that isn't done."""
        now = self.clock()
        with self._lock:
            vacated = self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            ok = (row is not None and row["claim"] == claim
                 and row["state"] == "running")
            if ok:
                duration = now - (row["started_at"] or now)
                self._conn.execute(
                    "UPDATE jobs SET state = 'done', stage = 'cache', "
                    "finished_at = ?, duration = ? WHERE id = ?",
                    (now, duration, job_id))
                self._conn.execute(
                    "INSERT INTO stage_events (job_id, stage, event, at) "
                    "VALUES (?, 'cache', 'finish', ?)", (job_id, now))
                if video is not None:
                    self._insert_video_locked(*video)
                self._conn.commit()
        self._notify_vacated(vacated)
        return ok

    def release(self, job_id: int, claim: str) -> bool:
        """A worker giving a job back cleanly (stopping, or the job was
        cancelled on the next heartbeat): back to queued at once, at the
        front of the line (its original queued_at)."""
        now = self.clock()
        with self._lock:
            vacated = self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            ok = (row is not None and row["claim"] == claim
                 and row["state"] == "running")
            if ok:
                self._conn.execute(
                    "UPDATE jobs SET state = 'queued', claim = NULL, "
                    "worker_id = NULL, last_heartbeat = NULL, "
                    "started_at = NULL WHERE id = ?", (job_id,))
                self._conn.commit()
        self._notify_vacated(vacated)
        if ok:
            self._vacate_one(job_id, claim)
        return ok

    def live_claims(self) -> set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, claim FROM jobs WHERE state = 'running' AND "
                "claim IS NOT NULL").fetchall()
        return {f"{r['id']}-{r['claim']}" for r in rows}

    # -- admin actions --------------------------------------------------

    def transition(self, job_id: int, action: str) -> tuple[bool, str]:
        now = self.clock()
        vacate: tuple[int, str] | None = None
        with self._lock:
            vacated = self._sweep_stale_locked(now)
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                self._notify_vacated(vacated)
                return False, "no such job"
            if row["state"] not in TRANSITIONS[action]:
                self._notify_vacated(vacated)
                return False, f"cannot {action} a {row['state']} job"
            if action == "retry":
                live = self._conn.execute(
                    "SELECT id, state FROM jobs WHERE key = ? AND state IN "
                    "('queued', 'running') AND id != ?",
                    (row["key"], job_id)).fetchone()
                if live is not None:
                    self._notify_vacated(vacated)
                    return False, (f"job #{live['id']} for this key is "
                                  f"already {live['state']}")
                self._conn.execute(
                    "UPDATE jobs SET state = 'queued', queued_at = ?, "
                    "claim = NULL, worker_id = NULL, last_heartbeat = NULL, "
                    "started_at = NULL, error = NULL, failed_stage = NULL, "
                    "stage = NULL WHERE id = ?", (now, job_id))
            elif action == "cancel":
                if row["state"] == "running":
                    vacate = (job_id, row["claim"])
                self._conn.execute(
                    "UPDATE jobs SET state = 'cancelled', finished_at = ?, "
                    "claim = NULL WHERE id = ?", (now, job_id))
            elif action == "requeue":
                vacate = (job_id, row["claim"])
                self._conn.execute(
                    "UPDATE jobs SET state = 'queued', claim = NULL, "
                    "worker_id = NULL, last_heartbeat = NULL, "
                    "started_at = NULL WHERE id = ?", (job_id,))
            self._conn.commit()
        self._notify_vacated(vacated)
        if vacate is not None and vacate[1]:
            self._vacate_one(*vacate)
        return True, ""

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            self._sweep_stale_locked(self.clock())
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def stage_events_for(self, job_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT stage, event, at FROM stage_events WHERE job_id = ? "
                "ORDER BY id", (job_id,)).fetchall()
        return [dict(r) for r in rows]

    def workers(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, last_seen FROM workers ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # -- internal --------------------------------------------------------

    def _sweep_stale_locked(self, now: float) -> list[tuple[int, str]]:
        """Must be called with self._lock already held. Requeues any
        running job whose heartbeat is older than heartbeat_timeout, and
        returns the (job_id, claim) pairs that were vacated."""
        cutoff = now - self.heartbeat_timeout
        rows = self._conn.execute(
            "SELECT id, claim, worker_id FROM jobs WHERE state = 'running' "
            "AND last_heartbeat IS NOT NULL AND last_heartbeat < ?",
            (cutoff,)).fetchall()
        vacated = [(r["id"], r["claim"]) for r in rows if r["claim"]]
        for row in rows:
            note = f"requeued: worker {row['worker_id']} missed heartbeats"
            self._conn.execute(
                "UPDATE jobs SET state = 'queued', claim = NULL, "
                "worker_id = NULL, last_heartbeat = NULL, started_at = NULL, "
                "error = ? WHERE id = ?", (note, row["id"]))
        if rows:
            self._conn.commit()
        return vacated

    def _notify_vacated(self, vacated: list[tuple[int, str]]) -> None:
        for job_id, claim in vacated:
            self._vacate_one(job_id, claim)

    def _vacate_one(self, job_id: int, claim: str) -> None:
        if self.on_vacate is not None:
            self.on_vacate(job_id, claim)
