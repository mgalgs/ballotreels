import http.client
import json
import socket
import time
import unittest

from ballotreels.site import server as site_server

from .test_serve_private import ServerTestCaseWithConfig

PROP_90 = "ca-2026-11-03-prop-90"
PROP_91 = "ca-2026-11-03-prop-91"
PROP_92 = "ca-2026-11-03-prop-92"

class FailedJobNotRetriggeredTest(ServerTestCaseWithConfig):
    def _job_for(self, contest):
        status, body, _ = self._public("POST", "/api/generate",
                                       {"contest": contest})
        self.assertEqual(status, 201)
        return body["job"]["id"]

    def test_failed_and_cancelled_answer_their_state(self):
        failed = self._job_for(PROP_90)
        claim = self.deps.queue.claim("w1")["claim"]
        self.deps.queue.fail(failed, claim, "script", "no script")
        cancelled = self._job_for(PROP_91)
        self.deps.queue.transition(cancelled, "cancel")
        for contest, state in ((PROP_90, "failed"), (PROP_91, "cancelled")):
            with self.subTest(state):
                status, body, _ = self._public("POST", "/api/generate",
                                               {"contest": contest})
                self.assertEqual(status, 409)
                self.assertEqual(body["status"], state)
                self.assertIsNone(body["job"])
        self.assertEqual(len(self.deps.queue.list_jobs()), 2)

    def test_admin_retry_still_works(self):
        job_id = self._job_for(PROP_90)
        self.deps.queue.transition(job_id, "cancel")
        status, _, _ = self._private("POST", f"/admin/api/jobs/{job_id}/retry")
        self.assertEqual(status, 200)
        status, body, _ = self._public("POST", "/api/generate",
                                       {"contest": PROP_90})
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["id"], job_id)


class GlobalGenerateCapTest(ServerTestCaseWithConfig):
    config_overrides = {"generate_limit": 5, "generate_global_limit": 2,
                        "trust_forwarded_for": True}

    def test_cap_spans_every_ip(self):
        statuses = [
            self._public("POST", "/api/generate", {"contest": c},
                         headers={"X-Forwarded-For": ip})[0]
            for c, ip in ((PROP_90, "2001:db8::1"), (PROP_91, "2001:db8::2"),
                          (PROP_92, "2001:db8::3"))]
        self.assertEqual(statuses, [201, 201, 429])

    def test_global_refusal_is_named(self):
        for c, ip in ((PROP_90, "2001:db8::1"), (PROP_91, "2001:db8::2")):
            self._public("POST", "/api/generate", {"contest": c},
                         headers={"X-Forwarded-For": ip})
        status, body, _ = self._public(
            "POST", "/api/generate", {"contest": PROP_92},
            headers={"X-Forwarded-For": "2001:db8::3"})
        self.assertEqual(status, 429)
        self.assertEqual(body["limit"], "global")


class RequestTimeoutTest(ServerTestCaseWithConfig):
    def test_handlers_have_a_timeout(self):
        self.assertEqual(site_server.PublicHandler.timeout, 30)
        self.assertEqual(site_server.PrivateHandler.timeout, 30)

    def test_trickling_client_is_dropped(self):
        old = site_server._JsonHandler.timeout
        site_server._JsonHandler.timeout = 0.3
        self.addCleanup(setattr, site_server._JsonHandler, "timeout", old)
        sock = socket.create_connection(("127.0.0.1", self.public_port),
                                        timeout=5)
        self.addCleanup(sock.close)
        sock.sendall(b"POST /api/generate HTTP/1.1\r\nHost: x\r\n"
                     b"Content-Length: 100\r\n\r\n{")
        start = time.monotonic()
        # The server gives up on the body and closes the connection.
        while sock.recv(4096):
            pass
        self.assertLess(time.monotonic() - start, 4)

    def _trickle(self, payload: bytes) -> float:
        """Sends payload a byte every 0.1 s (inside a 0.5 s idle timeout)
        until the server hangs up; returns how long that took."""
        for attr, value in (("timeout", 0.5), ("request_deadline", 1)):
            old = getattr(site_server._JsonHandler, attr)
            setattr(site_server._JsonHandler, attr, value)
            self.addCleanup(setattr, site_server._JsonHandler, attr, old)
        sock = socket.create_connection(("127.0.0.1", self.public_port),
                                        timeout=5)
        self.addCleanup(sock.close)
        start = time.monotonic()
        try:
            for i in range(len(payload)):
                sock.sendall(payload[i:i + 1])
                time.sleep(0.1)
                if time.monotonic() - start > 6:
                    break
            sock.shutdown(socket.SHUT_WR)
            while sock.recv(4096):
                pass
        except OSError:
            pass  # the server reset the connection: what we want
        return time.monotonic() - start

    def test_slowly_trickled_body_hits_the_deadline(self):
        body = json.dumps({"contest": "x" * 200}).encode()
        elapsed = self._trickle(
            b"POST /api/generate HTTP/1.1\r\nHost: x\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        self.assertLess(elapsed, 4)

    def test_slowly_trickled_headers_hit_the_deadline(self):
        elapsed = self._trickle(b"GET / HTTP/1.1\r\n" + b"X: y\r\n" * 50)
        self.assertLess(elapsed, 4)


if __name__ == "__main__":
    unittest.main()
