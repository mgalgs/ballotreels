import http.client
import io
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

import ballotreels.site.config as site_config
from ballotreels.cli import main
from ballotreels.queue import JobQueue, hash_for_key
from ballotreels.site.config import Config
from ballotreels.site.server import build_deps, make_servers

from . import geo_fixtures
from .helpers import REPO

FIXTURE_ELECTION = (REPO / "tests" / "fixtures" / "contests")


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _make_config(data_dir: Path, **overrides) -> Config:
    fields = dict(
        data_dir=data_dir, election="ca-2026-11-03",
        public_host="127.0.0.1", public_port=0,
        private_host="127.0.0.1", private_port=0,
        token="test-token", generate_limit=5, generate_window=3600,
        trust_forwarded_for=False, heartbeat_timeout=120.0,
        eta_default_minutes=10.0, max_upload_mb=500,
        # The queue-flow tests start jobs directly; the approval queue
        # (on by default) has its own tests in test_approval.
        require_approval=False)
    fields.update(overrides)
    return Config(**fields)


class ServerTestCase(unittest.TestCase):
    """Builds real geo data and starts both listeners on real sockets."""

    def setUp(self):
        self._old_data_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = FIXTURE_ELECTION
        self.addCleanup(self._restore_data_root)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name) / "var"
        geo_fixtures.build_fixture_geo(self.data_dir)

        self.config = _make_config(self.data_dir)
        self.deps = build_deps(self.config)
        self.public, self.private = make_servers(self.deps)
        self.addCleanup(self.deps.queue.close)
        self._threads = []
        for srv in (self.public, self.private):
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            self._threads.append(t)
        self.addCleanup(self._shutdown)

    def _restore_data_root(self):
        site_config.DATA_ROOT = self._old_data_root

    def _shutdown(self):
        self.public.shutdown()
        self.private.shutdown()
        self.public.server_close()
        self.private.server_close()

    def get(self, port, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def head(self, port, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("HEAD", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    @property
    def public_port(self):
        return self.public.server_address[1]

    @property
    def private_port(self):
        return self.private.server_address[1]


class ZipApiTest(ServerTestCase):
    def test_zip_api(self):
        resp, body = self.get(self.public_port, "/api/zip/99902")
        self.assertEqual(resp.status, 200)
        doc = json.loads(body)
        self.assertEqual(doc["ambiguous"], ["cd"])
        self.assertEqual(len(doc["kinds"]["cd"]), 2)

        resp, body = self.get(self.public_port, "/api/zip/abc")
        self.assertEqual(resp.status, 400)

        resp, body = self.get(self.public_port, "/api/zip/00000")
        self.assertEqual(resp.status, 404)

    def test_zip_shapes(self):
        resp, body = self.get(self.public_port, "/api/zip/99902/shapes?kind=cd")
        self.assertEqual(resp.status, 200)
        doc = json.loads(body)
        roles = [f["properties"].get("role") for f in doc["features"]]
        self.assertEqual(roles.count("zip"), 1)
        self.assertEqual(roles.count("district"), 2)


class BallotTest(ServerTestCase):
    def test_ballot(self):
        resp, body = self.get(
            self.public_port,
            "/api/ballot?d=ocd-division/country:us/state:ca/cd:1")
        self.assertEqual(resp.status, 200)
        doc = json.loads(body)
        all_ids = [c["id"] for lvl in doc["levels"] for c in lvl["contests"]]
        self.assertIn("ca-2026-11-03-prop-90", all_ids)
        self.assertIn("ca-2026-11-03-prop-92", all_ids)
        self.assertIn("ca-2026-11-03-prop-91", all_ids)
        statewide = next(lvl for lvl in doc["levels"] if lvl["level"] == "state")
        self.assertEqual([c["id"] for c in statewide["contests"]],
                         ["ca-2026-11-03-prop-92", "ca-2026-11-03-prop-90"])
        for lvl in doc["levels"]:
            for c in lvl["contests"]:
                if c["kind"] == "race":
                    self.assertEqual(c["status"], "unavailable")


class VideoServingTest(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.key = ("ca-2026-11-03",
                    "ocd-division/country:us/state:ca",
                    "ca-2026-11-03-prop-90", 2, 2)
        self.key_hash = hash_for_key(self.key)
        cache_dir = self.data_dir / "cache" / self.key_hash / "1"
        cache_dir.mkdir(parents=True)
        self.content = b"0123456789" * 10
        (cache_dir / "video.mp4").write_bytes(self.content)
        self.deps.queue.record_video(
            self.key, "local",
            {"video": f"/v/{self.key_hash}/1/video.mp4"}, [])

    def test_video_full(self):
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "video/mp4")
        self.assertEqual(resp.getheader("Accept-Ranges"), "bytes")
        self.assertEqual(resp.getheader("Content-Length"), str(len(self.content)))
        self.assertIsNotNone(resp.getheader("ETag"))
        self.assertEqual(resp.getheader("Cache-Control"),
                         "public, max-age=31536000, immutable")
        self.assertEqual(body, self.content)

    def test_video_range_prefix(self):
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4",
                              {"Range": "bytes=0-99"})
        self.assertEqual(resp.status, 206)
        self.assertEqual(resp.getheader("Content-Range"),
                         f"bytes 0-99/{len(self.content)}")
        self.assertEqual(len(body), 100)
        self.assertEqual(body, self.content[0:100])

    def test_video_range_suffix_from_start(self):
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4",
                              {"Range": "bytes=50-"})
        self.assertEqual(resp.status, 206)
        self.assertEqual(body, self.content[50:])

    def test_video_range_last_n(self):
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4",
                              {"Range": "bytes=-10"})
        self.assertEqual(resp.status, 206)
        self.assertEqual(body, self.content[-10:])
        self.assertEqual(resp.getheader("Content-Range"),
                         f"bytes {len(self.content) - 10}-"
                         f"{len(self.content) - 1}/{len(self.content)}")

    def test_video_range_out_of_bounds(self):
        n = len(self.content)
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4",
                              {"Range": f"bytes={n + 10}-"})
        self.assertEqual(resp.status, 416)
        self.assertEqual(resp.getheader("Content-Range"), f"bytes */{n}")

    def test_video_inverted_range_serves_full(self):
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4",
                              {"Range": "bytes=50-10"})
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Length"),
                         str(len(self.content)))
        self.assertEqual(body, self.content)

    def test_video_multi_range_serves_full(self):
        resp, body = self.get(self.public_port,
                              f"/v/{self.key_hash}/1/video.mp4",
                              {"Range": "bytes=0-9,20-29"})
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, self.content)

    def test_video_head(self):
        resp, body = self.head(self.public_port,
                               f"/v/{self.key_hash}/1/video.mp4")
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(resp.getheader("Content-Length"), str(len(self.content)))

    def test_video_unknown_hash(self):
        resp, body = self.get(self.public_port, "/v/" + "0" * 16 + "/1/video.mp4")
        self.assertEqual(resp.status, 404)


class PrivateAuthTest(ServerTestCase):
    def test_private_auth(self):
        cases = [
            ("/worker/claim", "POST"),
            ("/admin/api/jobs", "GET"),
        ]
        for path, method in cases:
            with self.subTest(path=path, no_auth=True):
                conn = http.client.HTTPConnection(
                    "127.0.0.1", self.private_port, timeout=5)
                conn.request(method, path)
                resp = conn.getresponse()
                resp.read()
                self.assertEqual(resp.status, 401)
                self.assertEqual(resp.getheader("WWW-Authenticate"), "Bearer")
                conn.close()

            with self.subTest(path=path, wrong_token=True):
                conn = http.client.HTTPConnection(
                    "127.0.0.1", self.private_port, timeout=5)
                conn.request(method, path,
                             headers={"Authorization": "Bearer wrong"})
                resp = conn.getresponse()
                resp.read()
                self.assertEqual(resp.status, 401)
                conn.close()

            with self.subTest(path=path, right_token=True):
                conn = http.client.HTTPConnection(
                    "127.0.0.1", self.private_port, timeout=5)
                conn.request(method, path,
                             headers={"Authorization": "Bearer test-token"})
                resp = conn.getresponse()
                resp.read()
                self.assertNotEqual(resp.status, 401)
                conn.close()


class RefusesWithoutTokenTest(unittest.TestCase):
    def setUp(self):
        self._old_data_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = FIXTURE_ELECTION
        self.addCleanup(self._restore)

    def _restore(self):
        site_config.DATA_ROOT = self._old_data_root

    def _run(self, token_env):
        import os
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name) / "var"
        port = _free_port()
        old = os.environ.get("BALLOTREELS_TOKEN")
        if token_env is None:
            os.environ.pop("BALLOTREELS_TOKEN", None)
        else:
            os.environ["BALLOTREELS_TOKEN"] = token_env
        try:
            out = io.StringIO()
            err = io.StringIO()
            code = main(["serve", "--data-dir", str(data_dir),
                        "--election", "ca-2026-11-03",
                        "--public-port", str(port)],
                       out=out, err=err)
        finally:
            if old is None:
                os.environ.pop("BALLOTREELS_TOKEN", None)
            else:
                os.environ["BALLOTREELS_TOKEN"] = old
        return code, err.getvalue(), port

    def test_unresolvable_election_exits_2(self):
        import os
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        # Two elections for one state: every election is served at once
        # now, but only one per state.
        for name in ("e1", "e2"):
            (root / name).mkdir()
            (root / name / "contests.toml").write_text(
                f'[election]\nid = "{name}"\n'
                f'state = "ocd-division/country:us/state:ca"\n'
                f'title = "T"\n', encoding="utf-8")
        site_config.DATA_ROOT = root
        old = os.environ.get("BALLOTREELS_TOKEN")
        os.environ["BALLOTREELS_TOKEN"] = "t"
        try:
            err = io.StringIO()
            code = main(["serve", "--data-dir", str(root / "var"),
                        "--public-port", "0", "--private-port", "0"],
                       out=io.StringIO(), err=err)
        finally:
            if old is None:
                os.environ.pop("BALLOTREELS_TOKEN", None)
            else:
                os.environ["BALLOTREELS_TOKEN"] = old
        self.assertEqual(code, 2)
        self.assertIn("two elections for state 'ca'", err.getvalue())
        self.assertIn(str(root / "e1"), err.getvalue())
        self.assertIn(str(root / "e2"), err.getvalue())

    def test_refuses_without_token(self):
        for token_env in (None, "   "):
            with self.subTest(token_env=repr(token_env)):
                code, err, port = self._run(token_env)
                self.assertEqual(code, 2)
                self.assertIn("BALLOTREELS_TOKEN is not set", err)
                with self.assertRaises(OSError):
                    socket.create_connection(("127.0.0.1", port), timeout=0.3)


class ConfigDefaultsTest(unittest.TestCase):
    def test_config_defaults_and_precedence(self):
        import argparse
        import os

        from ballotreels.site.config import REPO_ROOT, load_config

        ns = argparse.Namespace(
            data_dir=None, election=None, public_host=None,
            public_port=None, private_host=None, private_port=None,
            generate_limit=None, generate_window=None,
            trust_forwarded_for=None, heartbeat_timeout=None,
            eta_default_minutes=None, max_upload_mb=None)
        config = load_config(ns)
        self.assertEqual(config.data_dir, REPO_ROOT / "var")
        self.assertEqual(config.public_port, 8080)

        old_dir = os.environ.get("BALLOTREELS_DATA_DIR")
        old_port = os.environ.get("BALLOTREELS_PUBLIC_PORT")
        os.environ["BALLOTREELS_DATA_DIR"] = "/tmp/env-data-dir"
        os.environ["BALLOTREELS_PUBLIC_PORT"] = "9999"
        try:
            config = load_config(ns)
            self.assertEqual(config.data_dir, Path("/tmp/env-data-dir"))
            self.assertEqual(config.public_port, 9999)

            ns.data_dir = "/tmp/flag-data-dir"
            ns.public_port = 7777
            config = load_config(ns)
            self.assertEqual(config.data_dir, Path("/tmp/flag-data-dir"))
            self.assertEqual(config.public_port, 7777)
        finally:
            if old_dir is None:
                os.environ.pop("BALLOTREELS_DATA_DIR", None)
            else:
                os.environ["BALLOTREELS_DATA_DIR"] = old_dir
            if old_port is None:
                os.environ.pop("BALLOTREELS_PUBLIC_PORT", None)
            else:
                os.environ["BALLOTREELS_PUBLIC_PORT"] = old_port


if __name__ == "__main__":
    unittest.main()
