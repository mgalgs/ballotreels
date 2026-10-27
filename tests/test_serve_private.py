import http.client
import json
import threading
import time
import unittest

from ballotreels.index import key_for
from ballotreels.queue import hash_for_key

from .test_serve_public import ServerTestCase

TOKEN_HEADERS = {"Authorization": "Bearer test-token",
                 "Content-Type": "application/json"}


def _key(contest: str):
    return ("ca-2026-11-03", "ocd-division/country:us/state:ca", contest, 2, 2)


class PrivateApiMixin:
    """HTTP helpers shared by every test in this module; mixed into
    ServerTestCaseWithConfig, not a TestCase of its own."""

    def _private(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port,
                                          timeout=5)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        hdrs = dict(TOKEN_HEADERS)
        hdrs.update(headers or {})
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        parsed = json.loads(raw) if raw else None
        return resp.status, parsed, resp

    def _public(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.public_port,
                                          timeout=5)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        hdrs = {"Content-Type": "application/json"}
        hdrs.update(headers or {})
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        parsed = json.loads(raw) if raw else None
        return resp.status, parsed, resp


class ServerTestCaseWithConfig(PrivateApiMixin, ServerTestCase):
    """Lets subclasses override Config fields."""
    config_overrides: dict = {}

    def setUp(self):
        from . import geo_fixtures
        import ballotreels.site.config as site_config
        import tempfile
        from pathlib import Path
        from ballotreels.site.server import build_deps, make_servers
        from .test_serve_public import FIXTURE_ELECTION, _make_config

        self._old_data_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = FIXTURE_ELECTION
        self.addCleanup(self._restore_data_root)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name) / "var"
        geo_fixtures.build_fixture_geo(self.data_dir)

        self.config = _make_config(self.data_dir, **self.config_overrides)
        self.deps = build_deps(self.config)
        self.public, self.private = make_servers(self.deps)
        self.addCleanup(self.deps.queue.close)
        for srv in (self.public, self.private):
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
        self.addCleanup(self._shutdown)


class ClaimAtomicTest(ServerTestCaseWithConfig):
    def _claim(self, worker_id, barrier, results, index):
        barrier.wait()
        status, body, _ = self._private("POST", "/worker/claim",
                                        {"worker": worker_id})
        results[index] = (status, body)

    def test_claim_atomic_two_workers(self):
        for i in range(20):
            job, _ = self.deps.queue.create_job(_key(f"atomic1-{i}"))
            barrier = threading.Barrier(2)
            results = [None, None]
            t1 = threading.Thread(target=self._claim, args=("w1", barrier, results, 0))
            t2 = threading.Thread(target=self._claim, args=("w2", barrier, results, 1))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            statuses = sorted(r[0] for r in results)
            self.assertEqual(statuses, [200, 204])
            winner = results[0] if results[0][0] == 200 else results[1]
            self.assertEqual(winner[1]["job"]["id"], job["id"])

    def test_claim_atomic_two_jobs_two_workers(self):
        for i in range(20):
            job_a, _ = self.deps.queue.create_job(_key(f"atomic2a-{i}"))
            job_b, _ = self.deps.queue.create_job(_key(f"atomic2b-{i}"))
            barrier = threading.Barrier(2)
            results = [None, None]
            t1 = threading.Thread(target=self._claim, args=("w1", barrier, results, 0))
            t2 = threading.Thread(target=self._claim, args=("w2", barrier, results, 1))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            ids = {r[1]["job"]["id"] for r in results}
            self.assertEqual(ids, {job_a["id"], job_b["id"]})


class HeartbeatTimeoutTest(ServerTestCaseWithConfig):
    config_overrides = {"heartbeat_timeout": 0.2}

    def test_heartbeat_timeout_requeue(self):
        job, _ = self.deps.queue.create_job(_key("hbtimeout"))
        status1, body1, _ = self._private("POST", "/worker/claim", {"worker": "w1"})
        self.assertEqual(status1, 200)
        claim1 = body1["job"]["claim"]
        job_id = body1["job"]["id"]

        time.sleep(0.4)

        status2, body2, _ = self._private("POST", "/worker/claim", {"worker": "w2"})
        self.assertEqual(status2, 200)
        self.assertEqual(body2["job"]["id"], job_id)
        claim2 = body2["job"]["claim"]
        self.assertNotEqual(claim1, claim2)

        status, body, _ = self._private(
            "POST", f"/worker/jobs/{job_id}/heartbeat",
            {"claim": claim1, "stage": "render"})
        self.assertEqual(status, 409)

        status, body, _ = self._private(
            "POST", f"/worker/jobs/{job_id}/complete",
            {"claim": claim1, "storage": "local", "sources": []})
        self.assertEqual(status, 409)

        status, body, _ = self._private(
            "POST", f"/worker/jobs/{job_id}/fail",
            {"claim": claim1, "stage": "render", "output": "x"})
        self.assertEqual(status, 409)

        status = self._put_file(job_id, claim1, "video.mp4", b"x")
        self.assertEqual(status, 409)

        row = self.deps.queue.get_job(job_id)
        self.assertIn("missed heartbeats", row["error"])

    def _put_file(self, job_id, claim, name, data):
        import urllib.parse
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port,
                                          timeout=5)
        q = urllib.parse.quote(claim, safe="")
        conn.request("PUT", f"/worker/jobs/{job_id}/files/{name}?claim={q}",
                     body=data, headers={"Authorization": "Bearer test-token"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp.status


class UploadCompleteTest(ServerTestCaseWithConfig):
    def test_upload_and_complete(self):
        entry = self.deps.index.get("ca-2026-11-03-prop-90")
        key = key_for(self.deps.index.election.id, entry, self.deps.standard)
        self.deps.queue.create_job(key)
        status, body, _ = self._private("POST", "/worker/claim", {"worker": "w1"})
        self.assertEqual(status, 200)
        job_id = body["job"]["id"]
        claim = body["job"]["claim"]

        files = {"video.mp4": b"V" * 1000, "poster.jpg": b"\xff\xd8\xff\xd9",
                 "script.toml": b"x = 1\n", "sources.json": b"[]"}
        for name, content in files.items():
            conn = http.client.HTTPConnection("127.0.0.1", self.private_port,
                                              timeout=5)
            conn.request("PUT", f"/worker/jobs/{job_id}/files/{name}?claim={claim}",
                         body=content, headers=dict(TOKEN_HEADERS))
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 200)
            conn.close()

        status, body, _ = self._private(
            "POST", f"/worker/jobs/{job_id}/complete",
            {"claim": claim, "storage": "local", "sources": [{"id": "x"}]})
        self.assertEqual(status, 200)

        status, body, _ = self._public("GET", "/api/contest/ca-2026-11-03-prop-90")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "cached")
        self.assertIsNotNone(body["video_url"])

        conn = http.client.HTTPConnection("127.0.0.1", self.public_port, timeout=5)
        conn.request("GET", body["video_url"])
        resp = conn.getresponse()
        resp.read()
        self.assertEqual(resp.status, 200)
        conn.close()

    def test_complete_loses_race_with_cancel(self):
        # A cancel landing after complete's claim check but before the job
        # is marked done must leave no video recorded and answer 409.
        entry = self.deps.index.get("ca-2026-11-03-prop-91")
        key = key_for(self.deps.index.election.id, entry, self.deps.standard)
        self.deps.queue.create_job(key)
        status, body, _ = self._private("POST", "/worker/claim", {"worker": "w1"})
        job_id, claim = body["job"]["id"], body["job"]["claim"]
        for name in ("video.mp4", "poster.jpg", "script.toml", "sources.json"):
            conn = http.client.HTTPConnection("127.0.0.1", self.private_port,
                                              timeout=5)
            conn.request("PUT", f"/worker/jobs/{job_id}/files/{name}?claim={claim}",
                         body=b"x", headers=dict(TOKEN_HEADERS))
            conn.getresponse().read()
            conn.close()

        queue = self.deps.queue
        original = queue.complete

        def cancel_then_complete(*args, **kwargs):
            queue.transition(job_id, "cancel")
            return original(*args, **kwargs)

        queue.complete = cancel_then_complete
        try:
            status, _, _ = self._private(
                "POST", f"/worker/jobs/{job_id}/complete",
                {"claim": claim, "storage": "local", "sources": []})
        finally:
            queue.complete = original
        self.assertEqual(status, 409)
        self.assertEqual(queue.get_job(job_id)["state"], "cancelled")
        self.assertIsNone(queue.video_for(key))
        self.assertFalse(
            (self.deps.config.data_dir / "cache" / hash_for_key(key)).exists())


class UploadRejectionsTest(ServerTestCaseWithConfig):
    config_overrides = {"max_upload_mb": 1}

    def _claim_job(self, contest):
        self.deps.queue.create_job(_key(contest))
        status, body, _ = self._private("POST", "/worker/claim", {"worker": "w1"})
        self.assertEqual(status, 200)
        return body["job"]["id"], body["job"]["claim"]

    def test_missing_file_fails_complete(self):
        job_id, claim = self._claim_job("rej-missing")
        status, body, _ = self._private(
            "POST", f"/worker/jobs/{job_id}/complete",
            {"claim": claim, "storage": "local", "sources": []})
        self.assertEqual(status, 400)
        self.assertEqual(self.deps.queue.get_job(job_id)["state"], "running")

    def test_upload_no_content_length(self):
        job_id, claim = self._claim_job("rej-nolength")
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port, timeout=5)
        conn.putrequest("PUT", f"/worker/jobs/{job_id}/files/video.mp4?claim={claim}")
        conn.putheader("Authorization", "Bearer test-token")
        conn.endheaders()
        resp = conn.getresponse()
        resp.read()
        self.assertEqual(resp.status, 411)
        conn.close()

    def test_upload_over_limit(self):
        job_id, claim = self._claim_job("rej-toobig")
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port, timeout=5)
        body = b"x" * (2 * 1024 * 1024)
        conn.request("PUT", f"/worker/jobs/{job_id}/files/video.mp4?claim={claim}",
                     body=body, headers=dict(TOKEN_HEADERS))
        resp = conn.getresponse()
        resp.read()
        self.assertEqual(resp.status, 413)
        conn.close()

    def test_upload_claim_must_be_current_and_hex(self):
        job_id, claim = self._claim_job("rej-claim")
        put = HeartbeatTimeoutTest._put_file
        cases = {"wrong claim": (job_id, "0" * 32),
                 "path traversal": (job_id, "../../../escaped"),
                 "no such job": (999, "../../../escaped")}
        for label, (jid, c) in cases.items():
            with self.subTest(label):
                self.assertEqual(put(self, jid, c, "video.mp4", b"x"), 409)
        self.assertFalse((self.data_dir / "escaped").exists())
        self.assertFalse((self.data_dir / "cache" / "escaped").exists())
        self.assertEqual(put(self, job_id, claim, "video.mp4", b"x"), 200)

    def test_upload_bad_name(self):
        job_id, claim = self._claim_job("rej-badname")
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port, timeout=5)
        conn.request("PUT", f"/worker/jobs/{job_id}/files/evil.exe?claim={claim}",
                     body=b"x", headers=dict(TOKEN_HEADERS))
        resp = conn.getresponse()
        resp.read()
        self.assertEqual(resp.status, 404)
        conn.close()

    def test_complete_s3_non_http_url_rejected(self):
        job_id, claim = self._claim_job("rej-s3url")
        status, body, _ = self._private(
            "POST", f"/worker/jobs/{job_id}/complete",
            {"claim": claim, "storage": "s3", "sources": [],
             "objects": {"video": {"url": "ftp://bad"},
                        "poster": {"url": "https://ok.example/p.jpg"}}})
        self.assertEqual(status, 400)


class IncomingCleanupTest(ServerTestCaseWithConfig):
    def test_incoming_cleanup_on_cancel(self):
        self.deps.queue.create_job(_key("cleanup1"))
        status, body, _ = self._private("POST", "/worker/claim", {"worker": "w1"})
        job_id = body["job"]["id"]
        claim = body["job"]["claim"]
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port, timeout=5)
        conn.request("PUT", f"/worker/jobs/{job_id}/files/video.mp4?claim={claim}",
                     body=b"x", headers=dict(TOKEN_HEADERS))
        conn.getresponse().read()
        conn.close()

        incoming = self.data_dir / "cache" / ".incoming" / f"{job_id}-{claim}"
        self.assertTrue(incoming.is_dir())

        ok, _ = self.deps.queue.transition(job_id, "cancel")
        self.assertTrue(ok)
        self.assertFalse(incoming.exists())

    def test_startup_sweep(self):
        from ballotreels.site.server import build_deps

        orphan_incoming = self.data_dir / "cache" / ".incoming" / "999-deadbeef"
        orphan_incoming.mkdir(parents=True)
        (orphan_incoming / "video.mp4").write_bytes(b"x")

        orphan_cache = self.data_dir / "cache" / ("0" * 16)
        orphan_cache.mkdir(parents=True)

        deps2 = build_deps(self._make_test_config_for_sweep())
        self.addCleanup(deps2.queue.close)
        self.assertFalse(orphan_incoming.exists())
        self.assertFalse(orphan_cache.exists())

    def _make_test_config_for_sweep(self):
        from .test_serve_public import _make_config
        return _make_config(self.data_dir)


class GenerateRejectsTest(ServerTestCaseWithConfig):
    def test_generate_rejects_race(self):
        status, body, _ = self._public(
            "POST", "/api/generate", {"contest": "ca-2026-11-03-assembly-17"})
        self.assertEqual(status, 400)

    def test_generate_rejects_unknown(self):
        status, body, _ = self._public(
            "POST", "/api/generate", {"contest": "does-not-exist"})
        self.assertEqual(status, 404)


class RateLimitTest(ServerTestCaseWithConfig):
    config_overrides = {"generate_limit": 2, "generate_window": 3600}

    def test_rate_limit_blocks_after_limit(self):
        s1, b1, _ = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-90"})
        self.assertEqual(s1, 201)
        s2, b2, _ = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-91"})
        self.assertEqual(s2, 201)
        s3, b3, resp3 = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-92"})
        self.assertEqual(s3, 429)
        self.assertIsNotNone(resp3.getheader("Retry-After"))

    def test_rate_limit_join_allowed_after_limit(self):
        self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-90"})
        self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-91"})
        self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-92"})
        # Joining the still-live prop-90 job is allowed even over the limit.
        s, b, _ = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-90"})
        self.assertEqual(s, 200)

    def test_rate_limit_ignores_xff_when_untrusted(self):
        self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-90"},
                     headers={"X-Forwarded-For": "1.1.1.1"})
        self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-91"},
                     headers={"X-Forwarded-For": "2.2.2.2"})
        s, b, _ = self._public(
            "POST", "/api/generate", {"contest": "ca-2026-11-03-prop-92"},
            headers={"X-Forwarded-For": "3.3.3.3"})
        self.assertEqual(s, 429)


class RateLimitTrustedTest(ServerTestCaseWithConfig):
    config_overrides = {"generate_limit": 2, "generate_window": 3600,
                        "trust_forwarded_for": True}

    def test_rate_limit_separates_by_xff_when_trusted(self):
        s1, _, _ = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-90"},
                                headers={"X-Forwarded-For": "9.9.9.9, 1.2.3.4"})
        s2, _, _ = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-91"},
                                headers={"X-Forwarded-For": "9.9.9.9, 1.2.3.4"})
        s3, _, _ = self._public("POST", "/api/generate", {"contest": "ca-2026-11-03-prop-92"},
                                headers={"X-Forwarded-For": "9.9.9.9, 1.2.3.4"})
        self.assertEqual((s1, s2, s3), (201, 201, 429))

        # A different rightmost entry is a different bucket, so it is not
        # blocked even though the first bucket is already over the limit.
        job, _ = self.deps.queue.create_job(key_for(
            self.deps.index.election.id,
            self.deps.index.get("ca-2026-11-03-prop-92"), self.deps.standard))
        self.deps.queue.transition(job["id"], "cancel")
        s4, _, _ = self._public(
            "POST", "/api/generate", {"contest": "ca-2026-11-03-prop-92"},
            headers={"X-Forwarded-For": "9.9.9.9, 5.6.7.8"})
        self.assertEqual(s4, 201)


class BodyLimitTest(ServerTestCaseWithConfig):
    def _raw_public(self, body, headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.public_port,
                                          timeout=5)
        conn.request("POST", "/api/generate", body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp.status, raw

    def test_oversized_body_413_without_reading_it(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.public_port,
                                          timeout=5)
        conn.putrequest("POST", "/api/generate")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(10 ** 9))
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual(resp.status, 413)
        conn.close()

    def test_bad_json_400(self):
        for label, body in (("malformed", b"{nope"), ("array", b"[1, 2]")):
            with self.subTest(label):
                status, raw = self._raw_public(
                    body, {"Content-Type": "application/json"})
                self.assertEqual(status, 400)
                self.assertIn(b"JSON object", raw)


class JobStatusTest(ServerTestCaseWithConfig):
    def test_job_status_queued_running_done(self):
        key = _key("jobstatus")
        job, _ = self.deps.queue.create_job(key)
        status, body, _ = self._public("GET", f"/api/jobs/{job['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "queued")
        self.assertIn("position", body)
        self.assertIn("eta_minutes", body)

        claimed = self.deps.queue.claim("w1")
        status, body, _ = self._public("GET", f"/api/jobs/{job['id']}")
        self.assertEqual(body["state"], "running")

        self.deps.queue.complete(claimed["id"], claimed["claim"])
        self.deps.queue.record_video(key, "local", {"video": "/v/abc/video.mp4"}, [])
        status, body, _ = self._public("GET", f"/api/jobs/{job['id']}")
        self.assertEqual(body["state"], "done")
        self.assertEqual(body["video_url"], "/v/abc/video.mp4")


class ListenerSeparationTest(ServerTestCaseWithConfig):
    def test_public_does_not_serve_worker_or_admin(self):
        status, _, _ = self._public("GET", "/worker/claim")
        self.assertEqual(status, 404)
        status, _, _ = self._public("GET", "/admin/api/jobs")
        self.assertEqual(status, 404)

    def test_private_does_not_serve_generate(self):
        status, _, _ = self._private("POST", "/api/generate", {"contest": "x"})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
