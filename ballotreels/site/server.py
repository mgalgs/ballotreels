"""The serve tier's two listeners: public (the site and its API) and
private (the worker API and the queue monitor, token-guarded).

Both are plain `http.server.ThreadingHTTPServer`s sharing one `Deps` (one
job queue, one loaded contest index, one loaded geo lookup), since they
read and write the same state.
"""

from __future__ import annotations

import hmac
import json
import re
import shutil
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..geo.lookup import GeoData
from ..index import ContestIndex, ballot_order, key_for, level_of, load_index
from ..queue import JobQueue
from ..standard import Standard, load_standard
from .config import Config, resolve_election_dir, state_abbr

REPORT_URL = "https://github.com/mgalgs/ballotreels/issues"

UPLOAD_NAMES = ("video.mp4", "poster.jpg", "script.toml", "sources.json")


@dataclass
class Deps:
    config: Config
    queue: JobQueue
    index: ContestIndex
    standard: Standard
    geo: GeoData | None
    rate_lock: threading.Lock = field(default_factory=threading.Lock)
    rate_hits: dict[str, list[float]] = field(default_factory=dict)
    clock: Any = None

    def __post_init__(self):
        if self.clock is None:
            self.clock = time.time


def _incoming_dir(data_dir: Path, job_id: int, claim: str) -> Path:
    return data_dir / "cache" / ".incoming" / f"{job_id}-{claim}"


def _sweep_orphaned_dirs(data_dir: Path, queue: JobQueue) -> None:
    """On every start: drop an `.incoming/` upload directory whose job is
    no longer running under that claim, and a `cache/` directory with no
    matching `videos` row (R-Q8)."""
    incoming_root = data_dir / "cache" / ".incoming"
    if incoming_root.is_dir():
        live = queue.live_claims()
        for d in incoming_root.iterdir():
            if d.is_dir() and d.name not in live:
                shutil.rmtree(d, ignore_errors=True)
    cache_root = data_dir / "cache"
    if cache_root.is_dir():
        known = queue.known_hashes()
        for d in cache_root.iterdir():
            if d.is_dir() and d.name != ".incoming" and d.name not in known:
                shutil.rmtree(d, ignore_errors=True)


def build_deps(config: Config, clock=None) -> Deps:
    election_dir = resolve_election_dir(config.election)
    index = load_index(election_dir)
    standard = load_standard()
    geo = None
    abbr = state_abbr(index.election.state)
    if abbr:
        geo_dir = config.data_dir / "geo" / abbr
        if (geo_dir / "zips.json").is_file():
            geo = GeoData.load(geo_dir)
    queue = JobQueue(config.data_dir / "queue.sqlite3",
                     clock=clock or time.time,
                     heartbeat_timeout=config.heartbeat_timeout)
    queue.on_vacate = lambda job_id, claim: shutil.rmtree(
        _incoming_dir(config.data_dir, job_id, claim), ignore_errors=True)
    _sweep_orphaned_dirs(config.data_dir, queue)
    return Deps(config=config, queue=queue, index=index, standard=standard,
               geo=geo, clock=clock)


class BadRequest(Exception):
    """A request the handler refuses before routing it further: answered
    with `status` and `{"error": message}` by the dispatcher."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class _JsonHandler(BaseHTTPRequestHandler):
    # Largest JSON or form body read into memory. The public listener only
    # takes a contest id or an address; the private one also takes a
    # failed job's check output.
    max_body_bytes = 16 * 1024
    server: "_DepsServer"

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


def _contest_summary(entry, deps: Deps) -> dict[str, Any]:
    key = key_for(deps.index.election.id, entry, deps.standard)
    video = deps.queue.video_for(key) if key is not None else None
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "number": entry.number,
        "office": entry.office,
        "status": "unavailable" if key is None else
                  ("cached" if video else "none"),
        "video_url": (video.urls.get("video") if video else None),
    }


def _contest_detail(entry, deps: Deps) -> dict[str, Any]:
    key = key_for(deps.index.election.id, entry, deps.standard)
    video = deps.queue.video_for(key) if key is not None else None
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "number": entry.number,
        "office": entry.office,
        "status": "unavailable" if key is None else
                  ("cached" if video else "none"),
        "video_url": (video.urls.get("video") if video else None),
        "poster_url": (video.urls.get("poster") if video else None),
        "sources": (video.sources if video else []),
        "standard_version": deps.standard.version,
        "template_version": key[4] if key is not None else None,
        "corrections": [{"date": c.date, "note": c.note}
                        for c in entry.corrections],
        "report_url": REPORT_URL,
    }


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


def _check_rate_limit(deps: Deps, ip: str) -> tuple[bool, int]:
    """True if a new job may be created for this client now; otherwise
    False and the number of seconds to suggest waiting."""
    now = deps.clock()
    with deps.rate_lock:
        hits = deps.rate_hits.setdefault(ip, [])
        window_start = now - deps.config.generate_window
        hits[:] = [t for t in hits if t > window_start]
        if len(hits) >= deps.config.generate_limit:
            retry_after = int(hits[0] + deps.config.generate_window - now) + 1
            return False, max(retry_after, 1)
        hits.append(now)
        return True, 0


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
            m = re.fullmatch(r"/api/contest/([^/]+)", path)
            if m and method == "GET":
                return self._contest(m.group(1))
            m = re.fullmatch(r"/api/jobs/(\d+)", path)
            if m and method == "GET":
                return self._job_status(int(m.group(1)))
            if path == "/api/generate" and method == "POST":
                return self._generate()
            m = re.fullmatch(r"/v/([0-9a-f]{16})/(video\.mp4|poster\.jpg)",
                             path)
            if m and method in ("GET", "HEAD"):
                return self._video(m.group(1), m.group(2), method)
            return self._not_found()
        except BadRequest as e:
            self._json(e.status, {"error": e.message})
        except BrokenPipeError:
            pass

    def _zip(self, zip_code: str) -> None:
        if not re.fullmatch(r"\d{5}", zip_code):
            return self._json(400, {"error": "zip must be 5 digits"})
        deps = self.server.deps
        result = deps.geo.zip_districts(zip_code) if deps.geo else None
        if result is None:
            return self._json(404, {"error": "no district data for this zip"})
        self._json(200, result)

    def _zip_shapes(self, zip_code: str) -> None:
        if not re.fullmatch(r"\d{5}", zip_code):
            return self._json(400, {"error": "zip must be 5 digits"})
        deps = self.server.deps
        if deps.geo is None or deps.geo.zip_districts(zip_code) is None:
            return self._json(404, {"error": "no district data for this zip"})
        kind = self._query().get("kind", [None])[0]
        kinds = [kind] if kind else None
        self._json(200, deps.geo.zip_shapes(zip_code, kinds=kinds))

    def _ballot(self) -> None:
        deps = self.server.deps
        divisions: list[str] = []
        seen = set()
        for d in self._query().get("d", []):
            if d not in seen:
                seen.add(d)
                divisions.append(d)
            if len(divisions) >= 10:
                break
        wanted = set(divisions)
        wanted.add(deps.index.election.state)
        levels: list[dict[str, Any]] = []
        current = None
        bucket = None
        for entry in ballot_order(deps.index):
            if entry.division not in wanted:
                continue
            lvl = level_of(entry.division, deps.index.election.state)
            if lvl != current:
                bucket = {"level": lvl, "contests": []}
                levels.append(bucket)
                current = lvl
            bucket["contests"].append(_contest_summary(entry, deps))
        self._json(200, {"election": deps.index.election.id,
                         "levels": levels})

    def _contest(self, contest_id: str) -> None:
        deps = self.server.deps
        entry = deps.index.get(contest_id)
        if entry is None:
            return self._not_found()
        self._json(200, _contest_detail(entry, deps))

    def _video(self, key_hash: str, name: str, method: str) -> None:
        deps = self.server.deps
        video = deps.queue.video_for_hash(key_hash)
        if video is None:
            return self._not_found()
        path = deps.config.data_dir / "cache" / key_hash / name
        if not path.is_file():
            return self._not_found()
        content_type = "video/mp4" if name == "video.mp4" else "image/jpeg"
        _serve_file_range(self, path, content_type, method)

    def _generate(self) -> None:
        deps = self.server.deps
        body = self._read_json()
        contest_id = body.get("contest")
        entry = deps.index.get(contest_id) if contest_id else None
        if entry is None:
            return self._json(404, {"error": "no such contest"})
        key = key_for(deps.index.election.id, entry, deps.standard)
        if key is None:
            return self._json(400, {"error": "not available yet"})
        video = deps.queue.video_for(key)
        if video is not None:
            return self._json(200, {"job": None, "status": "cached",
                                   "video_url": video.urls.get("video")})
        existing = deps.queue.find_live_job(key)
        if existing is not None:
            return self._json(200, {"job": _job_view(existing, deps)})
        ip = _client_ip(self, deps)
        allowed, retry_after = _check_rate_limit(deps, ip)
        if not allowed:
            self.send_response(429)
            self.send_header("Retry-After", str(retry_after))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        job, created = deps.queue.create_job(key)
        self._json(201 if created else 200, {"job": _job_view(job, deps)})

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
            if part.startswith("ballotreels_admin="):
                cookie_token = part[len("ballotreels_admin="):]
                if hmac.compare_digest(cookie_token.encode(), token.encode()):
                    return True
        return False

    def _dispatch(self, method: str) -> None:
        try:
            if not self._authorized():
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Bearer")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            path = urllib.parse.urlsplit(self.path).path
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
            self._not_found()  # admin routes added with the monitor (C7)
        except BadRequest as e:
            self._json(e.status, {"error": e.message})
        except BrokenPipeError:
            pass

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
        length = int(length_header)
        max_bytes = deps.config.max_upload_mb * 1024 * 1024
        if length > max_bytes:
            self.rfile.read(length)
            self.send_response(413)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = self.rfile.read(length)
        dest_dir = _incoming_dir(deps.config.data_dir, job_id, claim)
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / name).write_bytes(body)
        self._json(200, {"ok": True})

    def _complete(self, job_id: int) -> None:
        deps = self.server.deps
        body = self._read_json()
        claim = body.get("claim")
        job = deps.queue.get_job(job_id)
        if job is None or job["claim"] != claim or job["state"] != "running":
            return self._state_conflict(job_id)
        storage = body.get("storage", "local")
        sources = body.get("sources", [])
        key_hash = job["key_hash"]
        if storage == "local":
            incoming = _incoming_dir(deps.config.data_dir, job_id, claim)
            missing = [n for n in UPLOAD_NAMES if not (incoming / n).is_file()]
            if missing:
                return self._json(
                    400, {"error": f"missing upload(s): {', '.join(missing)}"})
            urls = {"video": f"/v/{key_hash}/video.mp4",
                   "poster": f"/v/{key_hash}/poster.jpg"}
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
                                   video=(key, storage, urls, sources)):
            return self._state_conflict(job_id)
        if storage == "local":
            dest = deps.config.data_dir / "cache" / key_hash
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            incoming.replace(dest)
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
