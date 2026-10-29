"""The serve tier's two listeners: public (the site and its API) and
private (the worker API and the queue monitor, token-guarded).

Both are plain `http.server.ThreadingHTTPServer`s sharing one `Deps` (one
job queue, and one contest index and geo lookup per state served), since
they read and write the same state.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import os
import tempfile
import json
import math
import re
import shutil
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..geo.lookup import GeoData, ballot_division
from ..geo.states import STATE_NAMES, chambers, state_for_zip
from ..index import (ContestIndex, IndexEntry, ballot_order, key_for,
                     level_of, load_index, voters_line)
from ..crash_course import split_key_contest
from ..narration_store import MAX_TAKE_BYTES
from ..queue import TRANSITIONS, JobQueue
from ..related import load_related, related_to
from ..standard import Standard, load_standard
from . import config as site_config
from . import pages
from .config import (Config, ElectionResolutionError, resolve_election_dirs,
                     state_abbr)

REPORT_URL = "https://github.com/mgalgs/ballotreels/issues"

UPLOAD_NAMES = ("video.mp4", "poster.jpg", "script.toml", "sources.json")

STATIC_DIR = Path(__file__).resolve().parent / "static"

CONTENT_TYPE_BY_EXT = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}

# Files browsers and crawlers ask for at the site root, without reading
# the page's head; each is served from static/.
ROOT_FILES = {
    "/favicon.ico": "favicon.ico",
    "/favicon.svg": "favicon.svg",
    "/apple-touch-icon.png": "apple-touch-icon.png",
    "/site.webmanifest": "site.webmanifest",
}

ADMIN_COOKIE = "ballotreels_admin"

# The window of the global Generate cap.
HOUR = 3600
# The most divisions one ballot request may name: a zip's statewide,
# congressional, legislative and county ones, and every city and school
# district it overlaps.
MAX_BALLOT_DIVISIONS = 40

# A rate-limit bucket that is not a client IP.
GLOBAL_BUCKET = "*"

# Paths that are never a state's or a measure's page, whatever follows.
RESERVED_PREFIXES = ("/api/", "/static/", "/v/", "/admin", "/worker/")


@dataclass(frozen=True)
class StateElection:
    """One state's election: its contest index and its geo lookup (None
    if `geo build` has not been run for the state)."""
    abbr: str
    index: ContestIndex
    geo: GeoData | None

    @property
    def year(self) -> str:
        """The year of the election's date (its id ends with it), the
        year in its pages' paths."""
        return pages.election_year(self.index.election.id)

    def path(self) -> str:
        """The state page's short path, e.g. "/ut"."""
        return f"/{self.abbr}"

    def contest_path(self, entry: IndexEntry) -> str:
        """A contest's short path: /<st>/<year>/<id without its election
        prefix>, e.g. "/ut/2026/amendment-a"."""
        return pages.contest_path(self.abbr, self.index.election.id, entry.id)

    def counties(self) -> dict[str, dict[str, Any]]:
        """counties.json's counties (ballotreels.geo.counties), by
        OCD-ID, in name order: none without it."""
        return (self.geo.counties or {}) if self.geo else {}

    def county_path(self, county: str) -> str:
        """A county's page: /<st>/<year>/county/<its OCD-ID name, with
        hyphens>, e.g. "/ca/2026/county/san-luis-obispo". Under "county/",
        so no county can ever take a measure's path."""
        return f"/{self.abbr}/{self.year}/county/{_county_slug(county)}"

    def county_at(self, year: str, slug: str) -> str | None:
        """The county whose page has this year and slug."""
        if year != self.year:
            return None
        wanted = urllib.parse.unquote(slug).lower()
        return next((c for c in self.counties()
                     if urllib.parse.unquote(_county_slug(c)) == wanted),
                    None)

    def contest_at(self, year: str, slug: str) -> IndexEntry | None:
        """The contest whose short path has this year and slug."""
        if year != self.year:
            return None
        wanted = f"/{self.abbr}/{year}/{slug}"
        return next((e for e in self.index.entries
                     if self.contest_path(e) == wanted), None)


def _county_slug(county: str) -> str:
    """"ocd-division/country:us/state:ca/county:san_luis_obispo" ->
    "san-luis-obispo" (percent-encoded past ASCII)."""
    return urllib.parse.quote(county.rsplit(":", 1)[1].replace("_", "-"))


@dataclass
class Deps:
    config: Config
    queue: JobQueue
    # Abbreviation -> that state's election, every state served.
    states: dict[str, StateElection]
    standard: Standard
    rate_lock: threading.Lock = field(default_factory=threading.Lock)
    rate_hits: dict[str, list[float]] = field(default_factory=dict)
    global_hits: list[float] = field(default_factory=list)
    clock: Any = None
    # data/related.toml's groups of related measures, by group name.
    related: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self):
        if self.clock is None:
            self.clock = time.time

    def contest(self, contest_id: str
                ) -> tuple[StateElection, IndexEntry] | None:
        """The contest with this id, in whichever election has it (ids
        start with their election's id, so at most one does)."""
        for state in self.states.values():
            entry = state.index.get(contest_id)
            if entry is not None:
                return state, entry
        return None

    def zip_states(self, zip_code: str) -> list[StateElection]:
        """Every served state whose geo data has this zip."""
        return [s for s in self.states.values()
                if s.geo is not None and zip_code in s.geo.zips]


def _incoming_dir(data_dir: Path, job_id: int, claim: str) -> Path:
    return data_dir / "cache" / ".incoming" / f"{job_id}-{claim}"


def _narration_dir(data_dir: Path) -> Path:
    """The narration store: each take's audio as <sha256>.wav, written
    and read only through the private listener."""
    return data_dir / "narration"


def _local_video_path(key_hash: str, job_id: int | str, name: str) -> str:
    """The public path of a locally stored file. The job id is part of
    it, so a regenerated video gets a new URL rather than one that
    browsers already hold as `immutable`."""
    return f"/v/{key_hash}/{job_id}/{name}"


def _sweep_orphaned_dirs(data_dir: Path, queue: JobQueue) -> None:
    """On every start: drop an `.incoming/` upload directory whose job is
    no longer running under that claim, a narration upload's leftover
    temporary file, and anything under `cache/` that is not the current
    local video for a `videos` row (R-Q8)."""
    incoming_root = data_dir / "cache" / ".incoming"
    if incoming_root.is_dir():
        live = queue.live_claims()
        for d in incoming_root.iterdir():
            if d.is_dir() and d.name not in live:
                shutil.rmtree(d, ignore_errors=True)
    # a narration upload cut off before its rename
    for tmp in _narration_dir(data_dir).glob(".*.tmp"):
        tmp.unlink(missing_ok=True)
    cache_root = data_dir / "cache"
    if cache_root.is_dir():
        known = queue.known_hashes()
        for d in cache_root.iterdir():
            if not d.is_dir() or d.name == ".incoming":
                continue
            if d.name not in known:
                shutil.rmtree(d, ignore_errors=True)
                continue
            _drop_stale_job_dirs(d, queue.video_for_hash(d.name))


def _drop_stale_job_dirs(hash_dir: Path, video) -> None:
    """Remove every entry under `cache/<hash>/` except the job directory
    the key's current local video is served from."""
    for child in hash_dir.iterdir():
        current = (video is not None and video.storage == "local" and
                   video.urls.get("video") == _local_video_path(
                       hash_dir.name, child.name, "video.mp4"))
        if current:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def load_states(config: Config, warn=None) -> dict[str, StateElection]:
    """Every election to serve, by state. Two elections for one state is
    an error; a state with no geo data is only a warning (its zips are
    not found, the other states serve as usual)."""
    if warn is None:
        warn = lambda message: print(message, file=sys.stderr)
    states: dict[str, StateElection] = {}
    dirs: dict[str, Path] = {}
    for election_dir in resolve_election_dirs(config.election):
        index = load_index(election_dir)
        abbr = state_abbr(index.election.state)
        if abbr is None:
            raise ElectionResolutionError(
                f"{election_dir}: state {index.election.state!r} is not a "
                f"state OCD-ID")
        if abbr in dirs:
            # One per state, so one per state and year: page paths
            # (/<st>/<year>/...) never have to guess between two.
            raise ElectionResolutionError(
                f"two elections for state {abbr!r}: {dirs[abbr]} and "
                f"{election_dir}; pass --election to choose")
        dirs[abbr] = election_dir
        geo = None
        geo_dir = config.data_dir / "geo" / abbr
        if (geo_dir / "zips.json").is_file():
            geo = GeoData.load(geo_dir)
            if geo.counties is None:
                warn(f"warning: no counties.json for {abbr!r} at {geo_dir} "
                     f"(run `python -m ballotreels geo counties --state "
                     f"{abbr}`); it will have no county pages")
        else:
            warn(f"warning: no geo data for {abbr!r} at {geo_dir} (run "
                 f"`python -m ballotreels geo build --state {abbr}`); its "
                 f"zips will not be found")
        states[abbr] = StateElection(abbr=abbr, index=index, geo=geo)
    for abbr, state in states.items():
        if state.year is None:
            # The year is part of every page path of the election.
            raise ElectionResolutionError(
                f"{dirs[abbr]}: election id {state.index.election.id!r} "
                f"does not end with its date (YYYY-MM-DD)")
    return states


def build_deps(config: Config, clock=None, warn=None) -> Deps:
    states = load_states(config, warn)
    standard = load_standard()
    queue = JobQueue(config.data_dir / "queue.sqlite3",
                     clock=clock or time.time,
                     heartbeat_timeout=config.heartbeat_timeout)
    queue.on_vacate = lambda job_id, claim: shutil.rmtree(
        _incoming_dir(config.data_dir, job_id, claim), ignore_errors=True)
    _sweep_orphaned_dirs(config.data_dir, queue)
    # A live lookup of the data root, so tests can monkeypatch it. Ids of
    # elections not served are left out of each page's list, not errors.
    related = load_related(site_config.DATA_ROOT / "related.toml")
    return Deps(config=config, queue=queue, states=states, standard=standard,
               clock=clock, related=related)


class BadRequest(Exception):
    """A request the handler refuses before routing it further: answered
    with `status` and `{"error": message}` by the dispatcher."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class _DeadlineReader(io.RawIOBase):
    """The handler's socket as a raw stream whose every recv is bounded
    by both the handler's idle timeout and its request deadline, so a
    client that sends one byte just inside the idle timeout still runs
    out of time on the request as a whole."""

    def __init__(self, handler: "_JsonHandler"):
        super().__init__()
        self._handler = handler

    def readable(self) -> bool:
        return True

    def readinto(self, buf) -> int:
        handler = self._handler
        sock = handler.connection
        timeout = handler.timeout
        deadline = handler.read_deadline
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("request deadline passed")
            timeout = remaining if timeout is None else min(timeout,
                                                            remaining)
        sock.settimeout(timeout)
        try:
            return sock.recv_into(buf)
        finally:
            # Writes keep the plain idle timeout.
            sock.settimeout(handler.timeout)


class _JsonHandler(BaseHTTPRequestHandler):
    # Largest JSON or form body read into memory. The public listener only
    # takes a contest id; the private one also takes a failed job's
    # check output.
    max_body_bytes = 16 * 1024
    # Seconds a read or write on the connection may block, so a client
    # that trickles its request cannot hold a handler thread forever.
    timeout = 30
    # Seconds from the start of a request to the end of reading its
    # headers and body: the idle timeout alone resets on every byte.
    request_deadline = 30
    read_deadline: float | None = None
    server: "_DepsServer"

    def setup(self) -> None:
        super().setup()
        self.rfile.close()
        self.rfile = io.BufferedReader(_DeadlineReader(self))

    def handle_one_request(self) -> None:
        # Starts when the server begins waiting for the request line, so
        # it bounds a trickled header block as well as the body.
        self.read_deadline = time.monotonic() + self.request_deadline
        super().handle_one_request()

    def log_message(self, *a):  # keep test/CI output quiet
        pass

    def _json(self, status: int, obj: Any) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _not_found(self, message: str = "not found") -> None:
        self._json(404, {"error": message})

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)

    def _read_body(self) -> bytes:
        """The request body, at most max_body_bytes; raises BadRequest for
        a bad or oversized Content-Length without reading the body, so a
        client cannot make the server buffer an arbitrary amount."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise BadRequest(400, "bad Content-Length") from None
        if length < 0:
            raise BadRequest(400, "bad Content-Length")
        if length > self.max_body_bytes:
            self.close_connection = True
            raise BadRequest(413, "request body too large")
        return self.rfile.read(length) if length else b""

    def _read_json(self) -> dict[str, Any]:
        body = self._read_body()
        if not body:
            return {}
        try:
            doc = json.loads(body)
        except ValueError:
            raise BadRequest(400, "body must be a JSON object") from None
        if not isinstance(doc, dict):
            raise BadRequest(400, "body must be a JSON object")
        return doc

    def _read_form_or_json(self) -> dict[str, str]:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return self._read_json()
        raw = self._read_body()
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        return {k: v[0] for k, v in parsed.items()}

    def _serve_static(self, rel_path: str) -> bool:
        """Serves `<STATIC_DIR>/rel_path` if it resolves inside
        STATIC_DIR; returns False (the caller 404s) otherwise, so a
        `..` path traversal cannot escape the static directory."""
        rel_path = rel_path.lstrip("/") or "index.html"
        try:
            candidate = (STATIC_DIR / rel_path).resolve()
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return False
        if not candidate.is_file():
            return False
        data = candidate.read_bytes()
        content_type = CONTENT_TYPE_BY_EXT.get(
            candidate.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Unversioned URLs: without this a browser may keep serving the
        # style.css or app.js from before a deploy.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)
        return True

    def _generate(self, rate_limited: bool) -> None:
        """Creates (or joins, or reports the cached video for) the job
        for the posted contest. The operator's path passes
        rate_limited=False: it neither checks nor records the limits."""
        deps = self.server.deps
        body = self._read_json()
        contest_id = body.get("contest")
        found = (deps.contest(contest_id)
                 if isinstance(contest_id, str) else None)
        if found is None:
            return self._json(404, {"error": "no such contest"})
        state, entry = found
        key = key_for(state.index.election.id, entry, deps.standard)
        if key is None:
            return self._json(400, {"error": "not available yet"})
        video = deps.queue.video_for(key)
        if video is not None:
            return self._json(200, {"job": None, "status": "cached",
                                   "video_url": video.urls.get("video")})
        existing = deps.queue.find_live_job(key)
        if existing is not None:
            return self._json(200, {"job": _job_view(existing, deps)})
        # A job that failed or was cancelled stays that way until the
        # operator retries it from the queue monitor: each new attempt
        # spends paid narration.
        latest = deps.queue.latest_job(key)
        if latest is not None and latest["state"] in ("failed", "cancelled"):
            return self._json(409, {"job": None, "status": latest["state"],
                                    "error": "not available yet"})
        if rate_limited:
            ip = _client_ip(self, deps)
            allowed, retry_after, everyone = _check_rate_limit(deps, ip)
            if everyone:
                # Named, so the page does not blame this visitor for it.
                return _too_many(self, 429, retry_after,
                                 "too many videos requested this hour",
                                 limit="global")
            if not allowed:
                self.send_response(429)
                self.send_header("Retry-After", str(retry_after))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        # With approval on, a visitor's request waits for the operator.
        job, created = deps.queue.create_job(
            key, state="pending" if deps.config.require_approval else "queued")
        self._json(201 if created else 200, {"job": _job_view(job, deps)})


class _DepsServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_cls, deps: Deps):
        super().__init__(address, handler_cls)
        self.deps = deps


def _serve_file_range(handler: _JsonHandler, path: Path, content_type: str,
                      method: str) -> None:
    size = path.stat().st_size
    etag = f'"{path.stat().st_mtime_ns:x}-{size:x}"'
    start, end, status = 0, size - 1, 200
    range_header = handler.headers.get("Range")
    if range_header and "," not in range_header:
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if m:
            s, e = m.groups()
            if s == "" and e == "":
                pass
            elif s == "":
                length = int(e)
                if length > 0:
                    start = max(0, size - length)
                    status = 206
            else:
                start = int(s)
                if start >= size:
                    handler.send_response(416)
                    handler.send_header("Content-Range", f"bytes */{size}")
                    handler.send_header("Content-Length", "0")
                    handler.end_headers()
                    return
                end = int(e) if e != "" else size - 1
                if end < start:
                    # Invalid (RFC 9110 14.1.1): ignore it, send the whole file.
                    start, end = 0, size - 1
                else:
                    end = min(end, size - 1)
                    status = 206
    length = end - start + 1
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("ETag", etag)
    handler.send_header("Cache-Control", "public, max-age=31536000, immutable")
    handler.send_header("Content-Length", str(length))
    if status == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.end_headers()
    if method == "HEAD":
        return
    with path.open("rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(65536, remaining))
            if not chunk:
                break
            handler.wfile.write(chunk)
            remaining -= len(chunk)


def _contest_status(key, deps: Deps) -> tuple[str, Any, dict[str, Any] | None]:
    """(status, video, job_view): status is "unavailable" (no key, e.g. a
    race), "cached", "pending" (requested, awaiting approval), "queued",
    "running", "failed" or "cancelled" (its latest job, which only the
    operator can retry), or "none"."""
    if key is None:
        return "unavailable", None, None
    video = deps.queue.video_for(key)
    if video is not None:
        return "cached", video, None
    job = deps.queue.find_live_job(key)
    if job is not None:
        return job["state"], None, _job_view(job, deps)
    latest = deps.queue.latest_job(key)
    if latest is not None and latest["state"] in ("failed", "cancelled"):
        return latest["state"], None, None
    return "none", None, None


def _contest_summary(entry, state: StateElection,
                     deps: Deps) -> dict[str, Any]:
    key = key_for(state.index.election.id, entry, deps.standard)
    status, video, job = _contest_status(key, deps)
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "number": entry.number,
        "office": entry.office,
        "path": state.contest_path(entry),
        "status": status,
        "video_url": (video.urls.get("video") if video else None),
        "job": job,
        **_voters(entry),
        **_jurisdiction(entry, state),
    }


def _local_name(entry: IndexEntry, state: StateElection) -> str | None:
    """The display name of a county, city or school-district contest's
    division ("City of San Diego", from the geo build), or None for any
    other contest. Without geo data, a name made from the OCD-ID."""
    level = level_of(entry.division, state.index.election.state)
    if level not in ("county", "place", "school_district"):
        return None
    name = state.geo.names.get(entry.division) if state.geo else None
    if name:
        return name
    name = entry.division.rsplit(":", 1)[1].replace("_", " ").title()
    return f"{name} County" if level == "county" else name


def _jurisdiction(entry: IndexEntry,
                  state: StateElection) -> dict[str, str]:
    """A local contest names whose it is, so a voter told it "may be on
    your ballot" can settle that with their own address; any other has
    no `jurisdiction`."""
    name = _local_name(entry, state)
    return {"jurisdiction": name} if name else {}


def _where(entry: IndexEntry, state: StateElection) -> str:
    """Whose measure a page's title says it is: a special district's own
    name (its `voters`), a county's, city's or school district's, or the
    state's, never implying a local measure is statewide."""
    if entry.voters:
        return entry.voters.removeprefix("the ")
    return _local_name(entry, state) or _state_name(state.abbr)


def _voters(entry: IndexEntry) -> dict[str, str]:
    """A contest voted on in only part of its county says so: "Only
    voters in the Helix Water District vote on this." (ballotreels.index.
    voters_problem); any other has no `voters`."""
    return {"voters": voters_line(entry.voters)} if entry.voters else {}


def _crash_course(state: StateElection, deps: Deps) -> dict[str, Any] | None:
    """The state's crash course, for the top of its page: None when it has
    none (too few statewide measures). Its key hashes its members' scripts
    and narration, so a video made before any of them changed is never
    shown as this one."""
    entry = state.index.crash_course
    if entry is None:
        return None
    key = key_for(state.index.election.id, entry, deps.standard)
    status, video, job = _contest_status(key, deps)
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "measures": len(entry.members),
        "status": status,
        "video_url": (video.urls.get("video") if video else None),
        "poster_url": (video.urls.get("poster") if video else None),
        "chapters": ((video.chapters or []) if video else []),
        "sources": (video.sources if video else []),
        "job": job,
    }


def _related(entry, state: StateElection,
             deps: Deps) -> list[dict[str, Any]]:
    """The measures related to `entry` (data/related.toml) that are
    served: its own state's first, in ballot order (most local first),
    then the other states' by state name, each in ballot order."""
    found = []
    for contest_id in related_to(deps.related, entry.id):
        hit = deps.contest(contest_id)
        if hit is None:
            continue
        other_state, other = hit
        position = ballot_order(other_state.index).index(other)
        found.append((other_state.abbr != state.abbr,
                      _sort_name(other_state.abbr), position,
                      other_state, other))
    found.sort(key=lambda f: f[:3])
    return [{"id": other.id,
             "state": other_state.abbr,
             "state_name": pages.capitalize(_state_name(other_state.abbr)),
             "title": other.title,
             "path": other_state.contest_path(other)}
            for *_, other_state, other in found]


def _county_links(entry: IndexEntry,
                  state: StateElection) -> list[dict[str, str]]:
    """The county pages a county's, city's or school district's
    contest is listed on, by name: none for any other."""
    level = level_of(entry.division, state.index.election.state)
    if state.geo is None or level not in ("county", "place",
                                          "school_district"):
        return []
    counties = state.counties()
    return [{"name": counties[c]["name"], "path": state.county_path(c)}
            for c in state.geo.division_counties(entry.division)]


# A county page's groups, in order: the county's own measures, its
# cities', its school districts', and its special districts' (filed
# under the county, with `voters`).
COUNTY_LEVELS = ("county", "place", "school_district", "special")


def _county_measures(state: StateElection,
                     county: str) -> list[tuple[str, list[IndexEntry]]]:
    """Every measure voted on anywhere in `county` but the statewide
    ones, by COUNTY_LEVELS (each in ballot order), leaving out the empty
    levels: the county's own and its special districts', and those of
    every city and school district sharing ground with it
    (counties.json)."""
    members = set(state.counties()[county]["divisions"])
    buckets: dict[str, list[IndexEntry]] = {l: [] for l in COUNTY_LEVELS}
    for entry in ballot_order(state.index):
        if entry.kind != "measure":
            continue
        if entry.division == county:
            buckets["special" if entry.voters else "county"].append(entry)
        elif entry.division in members:
            buckets[level_of(entry.division,
                             state.index.election.state)].append(entry)
    return [(l, buckets[l]) for l in COUNTY_LEVELS if buckets[l]]


def _hero(state: StateElection, county: str | None = None) -> str | None:
    """The map at the top of a state's or county's page
    (pages.hero_svg); None without counties.json. The state's flag is
    used only if its file is there."""
    hero = state.geo.hero if state.geo else None
    if not hero or not hero.get("paths"):
        return None
    flag = pages.flag_path(state.abbr)
    flag_url = f"/static/{flag}" if (STATIC_DIR / flag).is_file() else None
    return pages.hero_svg(_hero_in_list_order(state, hero), county, flag_url)


def _mini(state: StateElection) -> dict[str, Any]:
    """The home page's icon for a state's button: `{"mini": {"width",
    "height", "path"}, "flag": its 160 px flag's URL or None}`, the
    state's coarse outline from counties.json; nothing from a build
    before it."""
    mini = state.geo.mini if state.geo else None
    if not mini or not mini.get("path"):
        return {}
    flag = pages.mini_flag_path(state.abbr)
    return {"mini": {k: mini[k] for k in ("width", "height", "path")},
            "flag": f"/static/{flag}" if (STATIC_DIR / flag).is_file()
            else None}


def _hero_in_list_order(state: StateElection, hero: dict) -> dict:
    """`hero` with its outlines in the order of the state API's
    `counties` list, so the state page's county picker (app.js) pairs
    the n-th path of the hero's #hero-counties with the n-th county,
    without the outlines being sent twice or keyed: a county with no
    outline gets an empty one, and any outline of no listed county
    comes after them all."""
    paths = hero["paths"]
    listed = state.counties()
    ordered = {c: paths.get(c, "") for c in listed}
    ordered.update((c, d) for c, d in paths.items() if c not in listed)
    return {**hero, "paths": ordered}


def _contest_detail(entry, state: StateElection,
                    deps: Deps) -> dict[str, Any]:
    key = key_for(state.index.election.id, entry, deps.standard)
    status, video, job = _contest_status(key, deps)
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "number": entry.number,
        "office": entry.office,
        "path": state.contest_path(entry),
        # The tab title the server renders for this page, so an in-app
        # visit and a fresh load show the same one.
        "page_title": pages.measure_meta(
            _where(entry, state), entry.title, "", None).title,
        "state": state.abbr,
        "state_name": _state_name(state.abbr),
        "election": state.index.election.id,
        "status": status,
        "video_url": (video.urls.get("video") if video else None),
        "poster_url": (video.urls.get("poster") if video else None),
        "sources": (video.sources if video else []),
        # Each section's start, for the page's chapter list: none for a
        # video rendered before the render wrote them.
        "chapters": ((video.chapters or []) if video else []),
        "standard_version": deps.standard.version,
        "template_version": key[4] if key is not None else None,
        "corrections": [{"date": c.date, "note": c.note}
                        for c in entry.corrections],
        "report_url": REPORT_URL,
        "job": job,
        # Measures on the same subject, each linking to its own page.
        "related": _related(entry, state, deps),
        # The county pages it is listed on.
        "counties": _county_links(entry, state),
        # only a choice question says so: a yes/no measure's detail is
        # as it always was
        **({"choice": True} if entry.choice else {}),
        **_voters(entry),
        **_jurisdiction(entry, state),
    }


MAX_CHAPTERS = 64
MAX_CHAPTER_TITLE = 200


def _valid_chapters(chapters: Any) -> bool:
    """A worker's chapters: a list of {"start": seconds, "title": text},
    starts from zero, in order."""
    if not isinstance(chapters, list) or len(chapters) > MAX_CHAPTERS:
        return False
    last = 0.0
    for c in chapters:
        if not isinstance(c, dict) or set(c) != {"start", "title"}:
            return False
        start, title = c["start"], c["title"]
        if (isinstance(start, bool) or not isinstance(start, (int, float))
                or not math.isfinite(start) or start < last):
            return False
        if (not isinstance(title, str) or not title.strip()
                or len(title) > MAX_CHAPTER_TITLE):
            return False
        last = start
    return True


def _job_view(job: dict[str, Any], deps: Deps) -> dict[str, Any]:
    view = {"id": job["id"], "state": job["state"], "stage": job["stage"]}
    if job["state"] in ("queued", "running"):
        view["position"] = (deps.queue.position_of(job["id"])
                            if job["state"] == "queued" else None)
        view["eta_minutes"] = deps.queue.eta_minutes(
            job, deps.config.eta_default_minutes)
    if job["state"] == "done":
        video = deps.queue.video_for_hash(job["key_hash"])
        view["video_url"] = video.urls.get("video") if video else None
    if job["state"] == "failed":
        view["failed_stage"] = job.get("failed_stage")
    return view


def _client_ip(handler: _JsonHandler, deps: Deps) -> str:
    if deps.config.trust_forwarded_for:
        xff = handler.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[-1].strip()
    return handler.client_address[0]


def _over_limit(hits: list[float], limit: int, window: float,
                now: float) -> int:
    """Drops hits older than the window; 0 if another fits under
    `limit`, else the seconds until one does. Call with rate_lock held."""
    hits[:] = [t for t in hits if t > now - window]
    if len(hits) < limit:
        return 0
    return max(int(hits[0] + window - now) + 1, 1)


def _check_rate_limit(deps: Deps, ip: str) -> tuple[bool, int, bool]:
    """True if a new job may be created for this client now; otherwise
    False, the number of seconds to suggest waiting, and whether the cap
    across every client (rather than the client's own limit) is what
    refused it. Both must allow it (a per-IP limit alone is beaten by
    rotating IPv6 addresses)."""
    now = deps.clock()
    config = deps.config
    with deps.rate_lock:
        hits = deps.rate_hits.setdefault(ip, [])
        own_wait = _over_limit(hits, config.generate_limit,
                               config.generate_window, now)
        global_wait = _over_limit(deps.global_hits,
                                  config.generate_global_limit, HOUR, now)
        if own_wait or global_wait:
            return False, max(own_wait, global_wait), bool(global_wait)
        hits.append(now)
        deps.global_hits.append(now)
        return True, 0, False


def _too_many(handler: "_JsonHandler", status: int, retry_after: int,
              message: str, **extra: Any) -> None:
    body = json.dumps({"error": message, **extra}).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Retry-After", str(retry_after))
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _not_covered(state: str | None) -> dict[str, Any]:
    """The 404 body for a place in no state served: names its state
    when it is known."""
    name = STATE_NAMES.get(state) if state else None
    return {"error": (f"We don't cover {name} yet" if name
                      else "We don't cover this zip yet"),
            "covered": False, "state": state if name else None,
            "state_name": name}


def _state_name(abbr: str) -> str:
    return STATE_NAMES.get(abbr, abbr.upper())


def _sort_name(abbr: str) -> str:
    """A state's name to sort by ("the District of Columbia" under D)."""
    return _state_name(abbr).removeprefix("the ")


def _statewide_measures(state: StateElection) -> list[IndexEntry]:
    index = state.index
    return [e for e in ballot_order(index)
            if e.kind == "measure" and e.division == index.election.state]


def _statewide_only(zip_code: str, state: StateElection) -> dict[str, Any]:
    """A zip answer with only the statewide division: enough for the
    ballot of a state whose election has nothing on it, whose zips need
    no district data."""
    return {"zip": zip_code, "state": state.abbr,
            "election": state.index.election.id,
            "kinds": {"state": [{"ocd_id": state.index.election.state,
                                 "name": "Statewide"}]},
            "ambiguous": [], "chambers": chambers(state.abbr)}


def _uncovered_zip(zip_code: str, deps: Deps) -> dict[str, Any]:
    """Why a zip has no data: its state (told by its first three digits)
    is not served, or it is but has no data for this zip."""
    state = state_for_zip(zip_code)
    if state is not None and state in deps.states:
        return {"error": "no district data for this zip", "covered": True}
    return _not_covered(state)


class PublicHandler(_JsonHandler):
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        path = urllib.parse.urlsplit(self.path).path
        deps = self.server.deps
        try:
            m = re.fullmatch(r"/api/zip/([^/]+)/shapes", path)
            if m and method == "GET":
                return self._zip_shapes(m.group(1))
            m = re.fullmatch(r"/api/zip/([^/]+)", path)
            if m and method == "GET":
                return self._zip(m.group(1))
            if path == "/api/ballot" and method == "GET":
                return self._ballot()
            if path == "/api/states" and method == "GET":
                return self._states()
            m = re.fullmatch(r"/api/state/([a-z]{2})", path)
            if m and method == "GET":
                return self._state(m.group(1))
            m = re.fullmatch(r"/api/contest/([^/]+)", path)
            if m and method == "GET":
                return self._contest(m.group(1))
            m = re.fullmatch(r"/api/contest/([a-z]{2})/(\d{4})/([^/]+)", path)
            if m and method == "GET":
                return self._contest_at(*m.groups())
            m = re.fullmatch(r"/api/county/([a-z]{2})/(\d{4})/([^/]+)", path)
            if m and method == "GET":
                return self._county(*m.groups())
            m = re.fullmatch(r"/api/jobs/(\d+)", path)
            if m and method == "GET":
                return self._job_status(int(m.group(1)))
            if path == "/api/generate" and method == "POST":
                return self._generate(rate_limited=True)
            m = re.fullmatch(
                r"/v/([0-9a-f]{16})/(\d+)/(video\.mp4|poster\.jpg)", path)
            if m and method in ("GET", "HEAD"):
                return self._video(m.group(1), m.group(2), m.group(3), method)
            if path.startswith("/static/") and method in ("GET", "HEAD"):
                if self._serve_static(path[len("/static/"):]):
                    return
                return self._not_found()
            if path in ROOT_FILES and method in ("GET", "HEAD"):
                self._serve_static(ROOT_FILES[path])
                return
            if path == "/robots.txt" and method in ("GET", "HEAD"):
                return self._text(".txt", pages.robots_txt(
                    deps.config.site_url))
            if path == "/sitemap.xml" and method in ("GET", "HEAD"):
                return self._text(".xml", pages.sitemap_xml(
                    deps.config.site_url, self._sitemap_paths()))
            if (method in ("GET", "HEAD") and
                    not path.startswith(RESERVED_PREFIXES)):
                return self._page(path)
            return self._not_found()
        except BadRequest as e:
            self._json(e.status, {"error": e.message})
        except BrokenPipeError:
            pass

    def _page(self, path: str) -> None:
        """A page of the one-page app (which reads the path): its own
        title and link-preview tags for the home, a state's and a
        measure's page; the app's not-found view, as a 404, for a path
        that names no served state or no contest in it."""
        deps = self.server.deps
        # Typed by hand from a video: /UT/ is /ut.
        normal = path.lower().rstrip("/") or "/"
        if normal != path and self._page_meta(normal) is not None:
            return self._redirect(normal)
        # The old shared link of a state's page.
        m = re.fullmatch(r"/state/([a-z]{2})", normal)
        if m and m.group(1) in deps.states:
            return self._redirect(deps.states[m.group(1)].path())
        meta = self._page_meta(path)
        if meta is None:
            return self._html(404, pages.not_found_meta(path))
        # A measure's page carries its related measures in the HTML too.
        measure = self._measure_at(path)
        main = (pages.related_html(_related(measure[1], measure[0], deps))
                if measure else "")
        self._html(200, meta, main)

    def _measure_at(self, path: str
                    ) -> tuple[StateElection, IndexEntry] | None:
        """The contest whose short path is `path`, or None."""
        m = re.fullmatch(r"/([a-z]{2})/(\d{4})/([^/]+)", path)
        if not m:
            return None
        state = self.server.deps.states.get(m.group(1))
        entry = state.contest_at(m.group(2), m.group(3)) if state else None
        return (state, entry) if entry is not None else None

    def _county_at(self, path: str) -> tuple[StateElection, str] | None:
        """The county whose page is at `path`, or None."""
        m = re.fullmatch(r"/([a-z]{2})/(\d{4})/county/([^/]+)", path)
        if not m:
            return None
        state = self.server.deps.states.get(m.group(1))
        county = state.county_at(m.group(2), m.group(3)) if state else None
        return (state, county) if county is not None else None

    def _page_meta(self, path: str) -> pages.PageMeta | None:
        """The tags of the page at `path`, or None if there is none."""
        deps = self.server.deps
        if path == "/":
            return pages.home_meta()
        m = re.fullmatch(r"/([a-z]{2})(?:/(\d{4}))?", path)
        if m:
            state = deps.states.get(m.group(1))
            if state is None or m.group(2) not in (None, state.year):
                return None
            return pages.state_meta(_state_name(state.abbr), path,
                                    len(_statewide_measures(state)))
        county = self._county_at(path)
        if county:
            state, county = county
            return pages.county_meta(
                state.counties()[county]["name"], _state_name(state.abbr),
                state.index.election.id, state.county_path(county),
                sum(len(e) for _, e in _county_measures(state, county)))
        measure = self._measure_at(path)
        if measure:
            state, entry = measure
            key = key_for(state.index.election.id, entry, deps.standard)
            video = deps.queue.video_for(key) if key is not None else None
            poster = video.urls.get("poster") if video else None
            return pages.measure_meta(
                _where(entry, state), entry.title, path, poster,
                choice=entry.choice,
                video=video.urls.get("video") if video else None,
                video_made=video.created_at if video else None)
        return None

    def _html(self, status: int, meta: pages.PageMeta,
              main: str = "") -> None:
        template = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        body = pages.render_page(template, meta,
                                 self.server.deps.config.site_url, main
                                 ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPE_BY_EXT[".html"])
        self.send_header("Content-Length", str(len(body)))
        # The tags follow the video (its poster), so always revalidate.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _sitemap_paths(self) -> list[str]:
        """Every page worth indexing: the home page, each served state's
        page, each measure's page, and each county's page, in the
        states' name order."""
        deps = self.server.deps
        paths = ["/"]
        for abbr in sorted(deps.states, key=_sort_name):
            state = deps.states[abbr]
            paths.append(state.path())
            paths.extend(state.contest_path(e) for e in ballot_order(state.index)
                         if e.kind == "measure")
            paths.extend(state.county_path(c) for c in state.counties())
        return paths

    def _text(self, ext: str, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_BY_EXT[ext])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _redirect(self, path: str) -> None:
        query = urllib.parse.urlsplit(self.path).query
        self.send_response(301)
        # Site-relative: the configured site URL is for previews only.
        self.send_header("Location", path + (f"?{query}" if query else ""))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _zip(self, zip_code: str) -> None:
        if not re.fullmatch(r"\d{5}", zip_code):
            return self._json(400, {"error": "zip must be 5 digits"})
        deps = self.server.deps
        found = deps.zip_states(zip_code)
        if not found:
            # A served state with nothing on its ballot needs no district
            # data: every zip in it has the same, empty, ballot.
            state = deps.states.get(state_for_zip(zip_code) or "")
            if state is not None and not state.index.entries:
                return self._json(200, _statewide_only(zip_code, state))
            return self._json(404, _uncovered_zip(zip_code, deps))
        if len(found) > 1:
            # A zip across a state line: the zip alone can't say which
            # state's ballot it is (`needs_address` is the flag's old
            # name, kept for the app).
            return self._json(200, {
                "zip": zip_code, "needs_address": True,
                "states": [{"state": s.abbr,
                            "name": STATE_NAMES.get(s.abbr, s.abbr)}
                           for s in found],
                "kinds": {}, "ambiguous": []})
        state = found[0]
        result = state.geo.zip_districts(zip_code)
        result["election"] = state.index.election.id
        self._json(200, result)

    def _zip_shapes(self, zip_code: str) -> None:
        if not re.fullmatch(r"\d{5}", zip_code):
            return self._json(400, {"error": "zip must be 5 digits"})
        deps = self.server.deps
        found = deps.zip_states(zip_code)
        if not found:
            return self._json(404, _uncovered_zip(zip_code, deps))
        if len(found) > 1:
            return self._json(409, {"error": "this zip spans states"})
        kind = self._query().get("kind", [None])[0]
        kinds = [kind] if kind else None
        self._json(200, found[0].geo.zip_shapes(zip_code, kinds=kinds))

    def _ballot(self) -> None:
        """The contests of the divisions `d`; those of the divisions also
        given as `p` (a zip's partial ones: ballotreels.geo.lookup) are
        marked `maybe`, on the ballot or not depending on the address."""
        deps = self.server.deps
        divisions: list[str] = []
        seen = set()
        query = self._query()
        for d in query.get("d", []):
            if d not in seen:
                seen.add(d)
                divisions.append(d)
            if len(divisions) >= MAX_BALLOT_DIVISIONS:
                break
        partial = set(query.get("p", [])[:MAX_BALLOT_DIVISIONS])
        # The ballot is the state's whose division came with it (the
        # statewide one always does); with one state served, that one.
        state = next((deps.states[a] for a in map(state_abbr, divisions)
                      if a in deps.states), None)
        if state is None and len(deps.states) == 1:
            state = next(iter(deps.states.values()))
        if state is None:
            return self._json(404, {"error": "no covered state in this "
                                             "ballot"})
        index = state.index
        # A district's contests are its 9-12-only territory's too
        # (ballot_division), and certain where any piece of the district
        # covers the whole zip.
        wanted = {ballot_division(d) for d in divisions}
        wanted.add(index.election.state)
        certain = {ballot_division(d) for d in divisions if d not in partial}
        maybe = {ballot_division(d) for d in partial} - certain
        levels: list[dict[str, Any]] = []
        current = None
        bucket = None
        for entry in ballot_order(index):
            if entry.division not in wanted:
                continue
            lvl = level_of(entry.division, index.election.state)
            if lvl != current:
                bucket = {"level": lvl, "contests": []}
                levels.append(bucket)
                current = lvl
            summary = _contest_summary(entry, state, deps)
            if entry.division in maybe:
                summary["maybe"] = True
            bucket["contests"].append(summary)
        self._json(200, {"election": index.election.id,
                         "state": state.abbr,
                         "state_name": _state_name(state.abbr),
                         # Nothing at all on this state's ballot (not
                         # just nothing for these districts).
                         "empty_election": not index.entries,
                         "chambers": chambers(state.abbr),
                         "levels": levels})

    def _states(self) -> None:
        deps = self.server.deps
        self._json(200, {"states": [
            {"state": abbr, "name": _state_name(abbr),
             "election": deps.states[abbr].index.election.id,
             **_mini(deps.states[abbr])}
            for abbr in sorted(deps.states, key=_sort_name)]})

    def _state(self, abbr: str) -> None:
        deps = self.server.deps
        state = deps.states.get(abbr)
        if state is None:
            return self._json(404, _not_covered(abbr))
        index = state.index
        contests = [_contest_summary(e, state, deps)
                    for e in _statewide_measures(state)]
        self._json(200, {"election": index.election.id,
                         "year": state.year,
                         "state": abbr, "state_name": _state_name(abbr),
                         "page_title": pages.state_meta(
                             _state_name(abbr), state.path(),
                             len(contests)).title,
                         "empty_election": not index.entries,
                         "chambers": chambers(abbr),
                         "levels": ([{"level": "state", "contests": contests}]
                                    if contests else []),
                         # one video through every statewide measure
                         "crash_course": _crash_course(state, deps),
                         # every county's page, by name
                         "counties": [{"name": c["name"],
                                       "path": state.county_path(oid)}
                                      for oid, c in state.counties().items()],
                         "hero": _hero(state)})

    def _county(self, abbr: str, year: str, slug: str) -> None:
        """A county's page: every local measure voted on anywhere in it
        (_county_measures), for /<st>/<year>/county/<slug>."""
        deps = self.server.deps
        state = deps.states.get(abbr)
        county = state.county_at(year, slug) if state else None
        if county is None:
            return self._not_found()
        index = state.index
        name = state.counties()[county]["name"]
        levels = [{"level": level,
                   "contests": [_contest_summary(e, state, deps)
                                for e in entries]}
                  for level, entries in _county_measures(state, county)]
        path = state.county_path(county)
        self._json(200, {"election": index.election.id,
                         "year": state.year,
                         "state": abbr, "state_name": _state_name(abbr),
                         "state_path": state.path(),
                         "county": county, "county_name": name,
                         "path": path,
                         "heading": pages.county_heading(
                             name, index.election.id),
                         "page_title": pages.county_meta(
                             name, _state_name(abbr), index.election.id,
                             path, 0).title,
                         "none_text": pages.no_county_measures(name),
                         "empty_election": not index.entries,
                         "chambers": chambers(abbr),
                         "levels": levels,
                         "hero": _hero(state, county)})

    def _contest(self, contest_id: str) -> None:
        deps = self.server.deps
        found = deps.contest(contest_id)
        if found is None:
            return self._not_found()
        state, entry = found
        self._json(200, _contest_detail(entry, state, deps))

    def _contest_at(self, abbr: str, year: str, slug: str) -> None:
        """A contest by its short path's parts (/ut/2026/amendment-a)."""
        state = self.server.deps.states.get(abbr)
        entry = state.contest_at(year, slug) if state else None
        if entry is None:
            return self._not_found()
        self._json(200, _contest_detail(entry, state, self.server.deps))

    def _video(self, key_hash: str, job_id: str, name: str,
               method: str) -> None:
        deps = self.server.deps
        video = deps.queue.video_for_hash(key_hash)
        # Only the key's current video: a superseded one is gone.
        if (video is None or video.storage != "local" or
                video.urls.get("video") != _local_video_path(
                    key_hash, job_id, "video.mp4")):
            return self._not_found()
        path = deps.config.data_dir / "cache" / key_hash / job_id / name
        if not path.is_file():
            return self._not_found()
        content_type = "video/mp4" if name == "video.mp4" else "image/jpeg"
        _serve_file_range(self, path, content_type, method)

    def _job_status(self, job_id: int) -> None:
        deps = self.server.deps
        job = deps.queue.get_job(job_id)
        if job is None:
            return self._not_found()
        self._json(200, _job_view(job, deps))


class PrivateHandler(_JsonHandler):
    max_body_bytes = 4 * 1024 * 1024

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def _authorized(self) -> bool:
        token = self.server.deps.config.token
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            if hmac.compare_digest(auth[len("Bearer "):].encode(),
                                   token.encode()):
                return True
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(f"{ADMIN_COOKIE}="):
                if hmac.compare_digest(part[len(ADMIN_COOKIE) + 1:].encode(),
                                       token.encode()):
                    return True
        return False

    def _dispatch(self, method: str) -> None:
        try:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/admin/login" and method in ("GET", "POST"):
                return self._login(method)
            if not self._authorized():
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Bearer")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path.startswith("/admin/static/"):
                if self._serve_static(path[len("/admin/static/"):]):
                    return
                return self._not_found()
            if path == "/admin/" and method == "GET":
                if self._serve_static("admin.html"):
                    return
                return self._not_found()
            m = re.fullmatch(
                r"/admin/api/jobs/(\d+)/"
                r"(approve|reject|retry|cancel|requeue|regenerate)",
                path)
            if m and method == "POST":
                return self._admin_action(int(m.group(1)), m.group(2))
            if path == "/admin/api/jobs" and method == "GET":
                return self._admin_jobs()
            # The operator queueing many contests at once: same job as
            # /api/generate, outside the public limits.
            if path == "/admin/api/generate" and method == "POST":
                return self._generate(rate_limited=False)
            if path == "/worker/claim" and method == "POST":
                return self._claim()
            m = re.fullmatch(r"/worker/jobs/(\d+)/heartbeat", path)
            if m and method == "POST":
                return self._heartbeat(int(m.group(1)))
            m = re.fullmatch(r"/worker/jobs/(\d+)/stage", path)
            if m and method == "POST":
                return self._stage_event(int(m.group(1)))
            m = re.fullmatch(
                rf"/worker/jobs/(\d+)/files/"
                rf"({'|'.join(re.escape(n) for n in UPLOAD_NAMES)})", path)
            if m and method == "PUT":
                return self._upload(int(m.group(1)), m.group(2))
            m = re.fullmatch(r"/worker/jobs/(\d+)/complete", path)
            if m and method == "POST":
                return self._complete(int(m.group(1)))
            m = re.fullmatch(r"/worker/jobs/(\d+)/fail", path)
            if m and method == "POST":
                return self._fail(int(m.group(1)))
            m = re.fullmatch(r"/worker/jobs/(\d+)/release", path)
            if m and method == "POST":
                return self._release(int(m.group(1)))
            # The narration store (ballotreels.narration_store): a take's
            # audio by its SHA-256.
            m = re.fullmatch(r"/worker/narration/([0-9a-f]{64})", path)
            if m and method == "PUT":
                return self._narration_put(m.group(1))
            if m and method in ("GET", "HEAD"):
                return self._narration_get(m.group(1), method)
            self._not_found()
        except BadRequest as e:
            self._json(e.status, {"error": e.message})
        except BrokenPipeError:
            pass

    def _login(self, method: str) -> None:
        if method == "GET":
            if self._serve_static("login.html"):
                return
            return self._not_found()
        form = self._read_form_or_json()
        token = form.get("token", "")
        if not token or not hmac.compare_digest(
                token.encode(), self.server.deps.config.token.encode()):
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(302)
        self.send_header("Location", "/admin/")
        self.send_header(
            "Set-Cookie",
            f"{ADMIN_COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/admin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _admin_jobs(self) -> None:
        deps = self.server.deps
        jobs = deps.queue.list_jobs()
        out = []
        for job in jobs:
            stages: dict[str, dict[str, float]] = {}
            for e in deps.queue.stage_events_for(job["id"]):
                stages.setdefault(e["stage"], {})[e["event"]] = e["at"]
            for times in stages.values():
                if "start" in times and "finish" in times:
                    times["duration"] = times["finish"] - times["start"]
            out.append({
                "id": job["id"], "key": job["key"], "state": job["state"],
                "stage": job["stage"], "stages": stages,
                "worker_id": job["worker_id"],
                "last_heartbeat": job["last_heartbeat"],
                "error": job["error"], "failed_stage": job["failed_stage"],
                "queued_at": job["queued_at"], "started_at": job["started_at"],
                "finished_at": job["finished_at"], "duration": job["duration"],
            })
        # Pending jobs first: they are what the operator has to act on.
        out.sort(key=lambda j: j["state"] != "pending")
        depth = sum(1 for j in jobs if j["state"] == "queued")
        pending = sum(1 for j in jobs if j["state"] == "pending")
        self._json(200, {"jobs": out, "depth": depth, "pending": pending,
                         "median_seconds": deps.queue.median_seconds(),
                         "workers": deps.queue.workers()})

    def _admin_action(self, job_id: int, action: str) -> None:
        if action == "regenerate":
            stale = self._stale_regenerate(job_id)
            if stale is not None:
                return self._json(409, {"error": stale})
        ok, message = self.server.deps.queue.transition(job_id, action)
        if not ok:
            return self._json(409, {"error": message})
        self._json(200, {"ok": True})

    def _stale_regenerate(self, job_id: int) -> str | None:
        """Why a regenerate of this job can only fail, or None if it can
        go ahead: a copy of a job made for other versions than this server
        makes its contest for now would be refused by every worker, and a
        contest no longer served has no current versions at all. Jobs the
        queue would refuse anyway are left to its own message."""
        deps = self.server.deps
        job = deps.queue.get_job(job_id)
        if job is None or job["state"] not in TRANSITIONS["regenerate"]:
            return None
        contest_id = split_key_contest(job["contest"])[0]
        found = deps.contest(contest_id)
        key = (key_for(found[0].index.election.id, found[1], deps.standard)
               if found is not None else None)
        if key is None:
            return (f"job #{job_id}'s contest {contest_id} is no longer "
                    f"served, so it cannot be regenerated")
        has = (job["standard_version"], job["template_version"])
        now = (key[3], key[4])
        if has != now:
            return (f"job #{job_id} was made for standard {has[0]} / "
                    f"template {has[1]}, but this server now makes "
                    f"standard {now[0]} / template {now[1]}; post the "
                    f"contest again to get a fresh job")
        return None

    def _state_conflict(self, job_id: int) -> None:
        job = self.server.deps.queue.get_job(job_id)
        self._json(409, {"state": job["state"] if job else "unknown"})

    def _claim(self) -> None:
        deps = self.server.deps
        body = self._read_json()
        worker_id = body.get("worker", "unknown")
        job = deps.queue.claim(worker_id)
        if job is None:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._json(200, {"job": {
            "id": job["id"], "claim": job["claim"],
            "election": job["election"], "contest": job["contest"],
            "division": job["division"],
            "standard_version": job["standard_version"],
            "template_version": job["template_version"],
        }})

    def _heartbeat(self, job_id: int) -> None:
        deps = self.server.deps
        body = self._read_json()
        ok = deps.queue.heartbeat(job_id, body.get("claim"), body.get("stage"))
        if not ok:
            return self._state_conflict(job_id)
        self._json(200, {"ok": True})

    def _stage_event(self, job_id: int) -> None:
        deps = self.server.deps
        body = self._read_json()
        ok = deps.queue.stage_event(job_id, body.get("claim"),
                                    body.get("stage"), body.get("event"))
        if not ok:
            return self._state_conflict(job_id)
        self._json(200, {"ok": True})

    def _upload(self, job_id: int, name: str) -> None:
        deps = self.server.deps
        claim = self._query().get("claim", [None])[0]
        # The claim names the upload directory, so it must be the hex token
        # the queue issued, and it must be this job's current claim.
        job = deps.queue.get_job(job_id)
        if (not claim or not re.fullmatch(r"[0-9a-f]{1,64}", claim)
                or job is None or job["claim"] != claim
                or job["state"] != "running"):
            self.close_connection = True
            return self._state_conflict(job_id)
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self.send_response(411)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            length = int(length_header)
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            return self._json(400, {"error": "bad Content-Length"})
        max_bytes = deps.config.max_upload_mb * 1024 * 1024
        if length > max_bytes:
            # Close rather than read (and drop) the body: reading it would
            # let a client tie the connection up for as long as it likes.
            self.send_response(413)
            self.send_header("Connection", "close")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # An authorized worker's upload may be large and slow; only the
        # idle timeout applies to it.
        self.read_deadline = None
        body = self.rfile.read(length)
        dest_dir = _incoming_dir(deps.config.data_dir, job_id, claim)
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / name).write_bytes(body)
        self._json(200, {"ok": True})

    def _narration_put(self, sha: str) -> None:
        """Store the body as the take `sha` names, if it is that take:
        hashed while it is read, refused (422) when it is not, written
        under a temporary name and renamed into place. A take already
        stored is left as it is (stored: false)."""
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self.send_response(411)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            length = int(length_header)
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            return self._json(400, {"error": "bad Content-Length"})
        if length > MAX_TAKE_BYTES:
            self.send_response(413)
            self.send_header("Connection", "close")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # As for a worker's upload: only the idle timeout applies.
        self.read_deadline = None
        store = _narration_dir(self.server.deps.config.data_dir)
        store.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=store, prefix=f".{sha}.",
                                   suffix=".tmp")
        # Answered once the temporary file is renamed or gone.
        status, reply = 500, {"error": "upload failed"}
        try:
            h = hashlib.sha256()
            left = length
            with os.fdopen(fd, "wb") as f:
                while left:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    h.update(chunk)
                    f.write(chunk)
                    left -= len(chunk)
            got = h.hexdigest()
            dest = store / f"{sha}.wav"
            if left:
                self.close_connection = True
                status, reply = 400, {"error": "body shorter than "
                                               "Content-Length"}
            elif got != sha:
                status, reply = 422, {"error": f"body's SHA-256 is {got}, "
                                               f"not {sha}"}
            elif dest.is_file():
                status, reply = 200, {"ok": True, "stored": False}
            else:
                os.replace(tmp, dest)
                status, reply = 200, {"ok": True, "stored": True}
        finally:
            Path(tmp).unlink(missing_ok=True)
        self._json(status, reply)

    def _narration_get(self, sha: str, method: str) -> None:
        path = _narration_dir(self.server.deps.config.data_dir) / f"{sha}.wav"
        try:
            f = path.open("rb")
        except FileNotFoundError:
            return self._not_found(f"no narration take {sha}")
        with f:
            size = os.fstat(f.fileno()).st_size
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if method != "HEAD":
                shutil.copyfileobj(f, self.wfile, 1 << 20)

    def _complete(self, job_id: int) -> None:
        deps = self.server.deps
        body = self._read_json()
        claim = body.get("claim")
        job = deps.queue.get_job(job_id)
        if job is None or job["claim"] != claim or job["state"] != "running":
            return self._state_conflict(job_id)
        storage = body.get("storage", "local")
        sources = body.get("sources", [])
        chapters = body.get("chapters")
        if chapters is not None and not _valid_chapters(chapters):
            return self._json(400, {"error": "bad chapters"})
        key_hash = job["key_hash"]
        if storage == "local":
            incoming = _incoming_dir(deps.config.data_dir, job_id, claim)
            missing = [n for n in UPLOAD_NAMES if not (incoming / n).is_file()]
            if missing:
                return self._json(
                    400, {"error": f"missing upload(s): {', '.join(missing)}"})
            urls = {"video": _local_video_path(key_hash, job_id, "video.mp4"),
                   "poster": _local_video_path(key_hash, job_id,
                                               "poster.jpg")}
        elif storage == "s3":
            objects = body.get("objects")
            if not objects:
                return self._json(400, {"error": "missing objects"})
            for want in ("video", "poster"):
                url = objects.get(want, {}).get("url", "")
                if not re.match(r"^https?://", url):
                    return self._json(
                        400, {"error": f"{want} url must be http(s)"})
            urls = {name: obj["url"] for name, obj in objects.items()}
        else:
            return self._json(400, {"error": f"unknown storage {storage!r}"})
        key = (job["election"], job["division"], job["contest"],
              job["standard_version"], job["template_version"])
        # The claim check, the videos row and the done state are one
        # transaction; the files move into the cache only once it has
        # committed, so a job that lost its claim meanwhile leaves the
        # cache as it was.
        if not deps.queue.complete(job_id, claim,
                                   video=(key, storage, urls, sources,
                                          chapters)):
            return self._state_conflict(job_id)
        if storage == "local":
            hash_dir = deps.config.data_dir / "cache" / key_hash
            dest = hash_dir / str(job_id)
            if dest.exists():
                shutil.rmtree(dest)
            hash_dir.mkdir(parents=True, exist_ok=True)
            incoming.replace(dest)
            # The video this one replaces (an earlier job for the key).
            _drop_stale_job_dirs(hash_dir, deps.queue.video_for_hash(key_hash))
        self._json(200, {"ok": True})

    def _fail(self, job_id: int) -> None:
        deps = self.server.deps
        body = self._read_json()
        ok = deps.queue.fail(job_id, body.get("claim"), body.get("stage"),
                            body.get("output", ""))
        if not ok:
            return self._state_conflict(job_id)
        self._json(200, {"ok": True})

    def _release(self, job_id: int) -> None:
        deps = self.server.deps
        body = self._read_json()
        ok = deps.queue.release(job_id, body.get("claim"))
        if not ok:
            return self._state_conflict(job_id)
        self._json(200, {"ok": True})


def make_servers(deps: Deps) -> tuple[_DepsServer, _DepsServer]:
    public = _DepsServer((deps.config.public_host, deps.config.public_port),
                        PublicHandler, deps)
    private = _DepsServer(
        (deps.config.private_host, deps.config.private_port),
        PrivateHandler, deps)
    return public, private


def run_forever(public: _DepsServer, private: _DepsServer) -> None:
    thread = threading.Thread(target=private.serve_forever, daemon=True)
    thread.start()
    try:
        public.serve_forever()
    finally:
        private.shutdown()
        public.server_close()
        private.server_close()
