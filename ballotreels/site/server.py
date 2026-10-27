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
import threading
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

_VIDEO_NAME_RE = re.compile(r"(video\.mp4|poster\.jpg)")


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
            import time
            self.clock = time.time


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
                     clock=clock or __import__("time").time)
    return Deps(config=config, queue=queue, index=index, standard=standard,
               geo=geo, clock=clock)


class _JsonHandler(BaseHTTPRequestHandler):
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
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b""

    def _read_json(self) -> Any:
        body = self._read_body()
        return json.loads(body) if body else {}


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
                return self._not_found()  # added with the job queue (C4)
            if path == "/api/generate" and method == "POST":
                return self._not_found()  # added with the job queue (C4)
            m = re.fullmatch(r"/v/([0-9a-f]{16})/(video\.mp4|poster\.jpg)",
                             path)
            if m and method in ("GET", "HEAD"):
                return self._video(m.group(1), m.group(2), method)
            return self._not_found()
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


class PrivateHandler(_JsonHandler):
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
            self._not_found()  # routes added with the worker API (C4+)
        except BrokenPipeError:
            pass


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
