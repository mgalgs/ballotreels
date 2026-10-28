import http.client
import unittest
import urllib.parse

from .test_serve_private import ServerTestCaseWithConfig, _key

TOKEN = "test-token"


def _key_for(contest: str):
    return _key(contest)


class AdminTestCase(ServerTestCaseWithConfig):
    def _admin(self, method, path, body=None, cookie=None, token=TOKEN):
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port,
                                          timeout=5)
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if cookie is not None:
            headers["Cookie"] = f"ballotreels_admin={cookie}"
        data = None
        if body is not None:
            data = urllib.parse.urlencode(body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp, raw

    def _admin_json(self, method, path, token=TOKEN):
        import json
        conn = http.client.HTTPConnection("127.0.0.1", self.private_port,
                                          timeout=5)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp, (json.loads(raw) if raw else None)


class JobsJsonTest(AdminTestCase):
    def test_jobs_json(self):
        job_q, _ = self.deps.queue.create_job(_key_for("admin-q"))
        job_r, _ = self.deps.queue.create_job(_key_for("admin-r"))
        claimed = self.deps.queue.claim("w1")
        job_f, _ = self.deps.queue.create_job(_key_for("admin-f"))
        claimed_f = self.deps.queue.claim("w1")
        self.deps.queue.fail(claimed_f["id"], claimed_f["claim"], "render",
                            "boom")

        resp, doc = self._admin_json("GET", "/admin/api/jobs")
        self.assertEqual(resp.status, 200)
        self.assertIn("depth", doc)
        self.assertIn("median_seconds", doc)
        self.assertIsInstance(doc["workers"], list)

        by_id = {j["id"]: j for j in doc["jobs"]}
        self.assertIn(job_q["id"], by_id)
        running = by_id[claimed["id"]]
        self.assertEqual(running["state"], "running")
        self.assertEqual(running["worker_id"], "w1")
        self.assertIn("last_heartbeat", running)

        failed = by_id[claimed_f["id"]]
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["error"], "boom")
        self.assertEqual(failed["failed_stage"], "render")
        self.assertIn("render", failed["stages"])


class RetryTest(AdminTestCase):
    def test_retry_failed(self):
        job, _ = self.deps.queue.create_job(_key_for("retry-failed"))
        claimed = self.deps.queue.claim("w1")
        self.deps.queue.fail(claimed["id"], claimed["claim"], "check", "nope")
        resp, _ = self._admin_json("POST", f"/admin/api/jobs/{job['id']}/retry")
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"], "queued")

    def test_retry_cancelled(self):
        job, _ = self.deps.queue.create_job(_key_for("retry-cancelled"))
        self.deps.queue.transition(job["id"], "cancel")
        resp, _ = self._admin_json("POST", f"/admin/api/jobs/{job['id']}/retry")
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"], "queued")


class CancelTest(AdminTestCase):
    def test_cancel_queued(self):
        job, _ = self.deps.queue.create_job(_key_for("cancel-queued"))
        resp, _ = self._admin_json("POST", f"/admin/api/jobs/{job['id']}/cancel")
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"],
                         "cancelled")

    def test_cancel_running(self):
        job, _ = self.deps.queue.create_job(_key_for("cancel-running"))
        claimed = self.deps.queue.claim("w1")
        resp, _ = self._admin_json("POST", f"/admin/api/jobs/{job['id']}/cancel")
        self.assertEqual(resp.status, 200)
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"],
                         "cancelled")
        self.assertFalse(self.deps.queue.heartbeat(
            claimed["id"], claimed["claim"], "render"))


class RequeueTest(AdminTestCase):
    def test_requeue_running(self):
        job, _ = self.deps.queue.create_job(_key_for("requeue-running"))
        original_queued_at = job["queued_at"]
        claimed = self.deps.queue.claim("w1")
        resp, _ = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/requeue")
        self.assertEqual(resp.status, 200)
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "queued")
        self.assertEqual(row["queued_at"], original_queued_at)
        self.assertFalse(self.deps.queue.heartbeat(
            claimed["id"], claimed["claim"], "render"))


PROP_90 = "ca-2026-11-03-prop-90"
CRASH_COURSE = "ca-2026-11-03-crash-course"


class RegenerateTest(AdminTestCase):
    def _current_key(self, contest):
        """The key a fresh post of this served contest gets now."""
        from ballotreels.index import key_for
        state, entry = self.deps.contest(contest)
        return key_for(state.index.election.id, entry, self.deps.standard)

    def _done_job(self, contest=None, key=None):
        key = key if key is not None else self._current_key(contest)
        job, _ = self.deps.queue.create_job(key)
        claimed = self.deps.queue.claim("w1")
        self.assertTrue(self.deps.queue.complete(
            claimed["id"], claimed["claim"],
            video=(key, "local", {"video": "/v/old/1/video.mp4"}, [])))
        return key, job

    def test_regenerate_done(self):
        # STANDARD.md rule 5.2: a correction is fixed by regenerating; the
        # old video keeps serving until the new job replaces it.
        key, job = self._done_job(PROP_90)
        resp, doc = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/regenerate")
        self.assertEqual(resp.status, 200, doc)
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"], "done")
        live = self.deps.queue.find_live_job(key)
        self.assertIsNotNone(live)
        self.assertNotEqual(live["id"], job["id"])
        self.assertEqual(live["state"], "queued")
        self.assertEqual(self.deps.queue.video_for(key).urls["video"],
                         "/v/old/1/video.mp4")

        resp, doc = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/regenerate")
        self.assertEqual(resp.status, 409)
        self.assertEqual(doc["error"],
                         f"job #{live['id']} for this key is already queued")

    def test_regenerate_current_crash_course(self):
        key, job = self._done_job(CRASH_COURSE)
        resp, doc = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/regenerate")
        self.assertEqual(resp.status, 200, doc)
        live = self.deps.queue.find_live_job(key)
        self.assertEqual(live["state"], "queued")
        self.assertNotEqual(live["id"], job["id"])

    def _assert_stale_refused(self, current, stale):
        _, job = self._done_job(key=stale)
        before = len(self.deps.queue.list_jobs())
        resp, doc = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/regenerate")
        self.assertEqual(resp.status, 409)
        self.assertEqual(doc["error"], (
            f"job #{job['id']} was made for standard {stale[3]} / "
            f"template {stale[4]}, but this server now makes standard "
            f"{current[3]} / template {current[4]}; post the contest "
            f"again to get a fresh job"))
        self.assertEqual(len(self.deps.queue.list_jobs()), before)
        self.assertIsNone(self.deps.queue.find_live_job(stale))

    def test_regenerate_refuses_older_template_crash_course(self):
        # 19 crash courses regenerated after the template went 2 -> 3 all
        # still said template 2, and every worker failed them.
        current = self._current_key(CRASH_COURSE)
        stale = current[:4] + (current[4] - 1,)
        self._assert_stale_refused(current, stale)

    def test_regenerate_refuses_older_template_measure(self):
        current = self._current_key(PROP_90)
        stale = current[:4] + (current[4] - 1,)
        self._assert_stale_refused(current, stale)

    def test_regenerate_refuses_older_standard(self):
        current = self._current_key(PROP_90)
        stale = current[:3] + (current[3] - 1, current[4])
        self._assert_stale_refused(current, stale)

    def test_regenerate_refuses_contest_no_longer_served(self):
        _, job = self._done_job(key=_key_for("ca-2026-11-03-prop-999"))
        before = len(self.deps.queue.list_jobs())
        resp, doc = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/regenerate")
        self.assertEqual(resp.status, 409)
        self.assertEqual(doc["error"], (
            f"job #{job['id']}'s contest ca-2026-11-03-prop-999 is no "
            f"longer served, so it cannot be regenerated"))
        self.assertEqual(len(self.deps.queue.list_jobs()), before)

    def test_regenerate_only_from_done(self):
        job, _ = self.deps.queue.create_job(_key_for("regen-queued"))
        resp, doc = self._admin_json(
            "POST", f"/admin/api/jobs/{job['id']}/regenerate")
        self.assertEqual(resp.status, 409)
        self.assertEqual(doc["error"], "cannot regenerate a queued job")
        self.deps.queue.transition(job["id"], "cancel")


class InvalidTransitionsTest(AdminTestCase):
    def test_invalid_transitions(self):
        with self.subTest("retry on done"):
            job, _ = self.deps.queue.create_job(_key_for("inv-done"))
            claimed = self.deps.queue.claim("w1")
            self.assertEqual(claimed["id"], job["id"])
            self.deps.queue.complete(claimed["id"], claimed["claim"])
            resp, _ = self._admin_json(
                "POST", f"/admin/api/jobs/{job['id']}/retry")
            self.assertEqual(resp.status, 409)

        with self.subTest("requeue on queued"):
            job, _ = self.deps.queue.create_job(_key_for("inv-queued"))
            resp, _ = self._admin_json(
                "POST", f"/admin/api/jobs/{job['id']}/requeue")
            self.assertEqual(resp.status, 409)
            self.deps.queue.transition(job["id"], "cancel")  # don't leak

        with self.subTest("cancel on failed"):
            job, _ = self.deps.queue.create_job(_key_for("inv-failed"))
            claimed = self.deps.queue.claim("w1")
            self.assertEqual(claimed["id"], job["id"])
            self.deps.queue.fail(claimed["id"], claimed["claim"], "check", "x")
            resp, _ = self._admin_json(
                "POST", f"/admin/api/jobs/{job['id']}/cancel")
            self.assertEqual(resp.status, 409)

        with self.subTest("retry while key is live"):
            key = _key_for("inv-live")
            job1, _ = self.deps.queue.create_job(key)
            claimed = self.deps.queue.claim("w1")
            self.assertEqual(claimed["id"], job1["id"])
            self.deps.queue.fail(claimed["id"], claimed["claim"], "check", "x")
            job2, _ = self.deps.queue.create_job(key)  # the dedupe key is free now
            resp, _ = self._admin_json(
                "POST", f"/admin/api/jobs/{job1['id']}/retry")
            self.assertEqual(resp.status, 409)


class LoginCookieTest(AdminTestCase):
    def test_login_cookie(self):
        resp, body = self._admin("POST", "/admin/login", {"token": TOKEN},
                                 token=None)
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/admin/")
        set_cookie = resp.getheader("Set-Cookie")
        self.assertIn("ballotreels_admin=test-token", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Strict", set_cookie)

        resp, body = self._admin("POST", "/admin/login", {"token": "wrong"},
                                 token=None)
        self.assertEqual(resp.status, 401)
        self.assertIsNone(resp.getheader("Set-Cookie"))

        resp, body = self._admin("GET", "/admin/api/jobs", cookie=TOKEN,
                                 token=None)
        self.assertEqual(resp.status, 200)


class AdminPageTest(AdminTestCase):
    def test_admin_page(self):
        resp, body = self._admin("GET", "/admin/", cookie=TOKEN, token=None)
        self.assertEqual(resp.status, 200)
        self.assertIn(b"admin.js", body)


if __name__ == "__main__":
    unittest.main()
