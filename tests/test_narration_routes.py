"""The narration store's routes on the private listener
(/worker/narration/<sha256>): token-guarded, hash-checked, atomic, and
absent from the public listener."""

import hashlib
import http.client

from ballotreels.narration_store import MAX_TAKE_BYTES

from .test_serve_private import ServerTestCaseWithConfig

TAKE = b"RIFF" + bytes(range(256)) * 64
SHA = hashlib.sha256(TAKE).hexdigest()


class NarrationRoutesTest(ServerTestCaseWithConfig):
    def request(self, method, path, body=None, token="test-token",
                port=None, headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", port or self.private_port, timeout=5)
        hdrs = {"Authorization": f"Bearer {token}"} if token else {}
        hdrs.update(headers or {})
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp.status, raw, resp

    def stored(self, sha=SHA):
        return self.data_dir / "narration" / f"{sha}.wav"

    def test_good_upload_is_stored(self):
        status, raw, _ = self.request("PUT", f"/worker/narration/{SHA}", TAKE)
        self.assertEqual(status, 200, raw)
        self.assertIn(b'"stored": true', raw)
        self.assertEqual(self.stored().read_bytes(), TAKE)
        # nothing left beside it
        self.assertEqual([p.name for p in self.stored().parent.iterdir()],
                         [self.stored().name])

    def test_hash_mismatch_is_refused(self):
        other = "0" * 64
        status, raw, _ = self.request("PUT", f"/worker/narration/{other}",
                                      TAKE)
        self.assertEqual(status, 422, raw)
        self.assertIn(SHA.encode(), raw)
        self.assertFalse(self.stored(other).exists())
        self.assertEqual(list(self.stored().parent.iterdir()), [])

    def test_missing_token_is_refused(self):
        for method, body in (("PUT", TAKE), ("GET", None), ("HEAD", None)):
            status, _, _ = self.request(method, f"/worker/narration/{SHA}",
                                        body, token=None)
            self.assertEqual(status, 401, method)
        status, _, _ = self.request("PUT", f"/worker/narration/{SHA}", TAKE,
                                    token="wrong")
        self.assertEqual(status, 401)
        self.assertFalse(self.stored().exists())

    def test_repeat_upload_is_idempotent(self):
        self.request("PUT", f"/worker/narration/{SHA}", TAKE)
        mtime = self.stored().stat().st_mtime_ns
        status, raw, _ = self.request("PUT", f"/worker/narration/{SHA}", TAKE)
        self.assertEqual(status, 200, raw)
        self.assertIn(b'"stored": false', raw)
        self.assertEqual(self.stored().stat().st_mtime_ns, mtime)
        self.assertEqual(self.stored().read_bytes(), TAKE)

    def test_download(self):
        status, _, _ = self.request("GET", f"/worker/narration/{SHA}")
        self.assertEqual(status, 404)
        status, _, _ = self.request("HEAD", f"/worker/narration/{SHA}")
        self.assertEqual(status, 404)
        self.request("PUT", f"/worker/narration/{SHA}", TAKE)
        status, raw, resp = self.request("GET", f"/worker/narration/{SHA}")
        self.assertEqual(status, 200)
        self.assertEqual(raw, TAKE)
        self.assertEqual(resp.getheader("Content-Type"), "audio/wav")
        status, raw, resp = self.request("HEAD", f"/worker/narration/{SHA}")
        self.assertEqual(status, 200)
        self.assertEqual(raw, b"")
        self.assertEqual(resp.getheader("Content-Length"), str(len(TAKE)))

    def test_oversized_upload_is_refused_unread(self):
        status, _, _ = self.request(
            "PUT", f"/worker/narration/{SHA}", b"",
            headers={"Content-Length": str(MAX_TAKE_BYTES + 1)})
        self.assertEqual(status, 413)

    def test_bad_hash_in_path_is_not_a_route(self):
        for path in ("/worker/narration/abc", f"/worker/narration/{SHA}x",
                     f"/worker/narration/{SHA.upper()}",
                     f"/worker/narration/../{SHA}"):
            status, _, _ = self.request("PUT", path, TAKE)
            self.assertEqual(status, 404, path)

    def test_not_on_the_public_listener(self):
        self.request("PUT", f"/worker/narration/{SHA}", TAKE)
        for method, body in (("GET", None), ("HEAD", None), ("PUT", TAKE),
                             ("POST", TAKE)):
            status, raw, _ = self.request(
                method, f"/worker/narration/{SHA}", body,
                port=self.public_port)
            self.assertNotEqual(status, 200, method)
            self.assertNotIn(TAKE, raw)
        status, raw, _ = self.request("GET", f"/worker/narration/{SHA}",
                                      port=self.public_port, token=None)
        self.assertNotEqual(status, 200)
        self.assertNotIn(TAKE, raw)

    def test_leftover_temp_files_swept_on_start(self):
        from ballotreels.site.server import _sweep_orphaned_dirs
        store = self.data_dir / "narration"
        store.mkdir(parents=True, exist_ok=True)
        (store / f".{SHA}.abc.tmp").write_bytes(b"partial")
        self.stored().write_bytes(TAKE)
        _sweep_orphaned_dirs(self.data_dir, self.deps.queue)
        self.assertEqual([p.name for p in store.iterdir()],
                         [self.stored().name])
