"""The SQLite-backed store behind the serve tier.

One connection per process, guarded by a lock for our own compound
read-modify-write operations (SQLite serializes writers on its own, but
a "join a live job or create one" decision needs to be atomic across
more than one statement). WAL mode so the queue survives a restart
without losing anything committed.

This starts with just the cache of finished videos (the serve tier's own
read path); the job queue itself (jobs, stages, workers) is added
alongside the worker API.
"""

from __future__ import annotations

import hashlib
import json
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
"""


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
                clock: Callable[[], float] = time.time):
        self.clock = clock
        self._lock = threading.Lock()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_video(self, key: tuple[str, str, str, int, int], storage: str,
                     urls: dict[str, str],
                     sources: list[dict[str, Any]]) -> None:
        key_hash = hash_for_key(key)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO videos "
                "(key_hash, key, election, division, contest, "
                "standard_version, template_version, storage, urls, "
                "sources, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key_hash, key_string(key), *key, storage, json.dumps(urls),
                 json.dumps(sources), self.clock()))
            self._conn.commit()

    def video_for(self, key: tuple[str, str, str, int, int]) -> Video | None:
        return self.video_for_hash(hash_for_key(key))

    def video_for_hash(self, key_hash: str) -> Video | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT key_hash, key, storage, urls, sources, created_at "
                "FROM videos WHERE key_hash = ?", (key_hash,)).fetchone()
        if row is None:
            return None
        return Video(key_hash=row[0], key=row[1], storage=row[2],
                    urls=json.loads(row[3]), sources=json.loads(row[4]),
                    created_at=row[5])
