"""The approval queue: a visitor's request waits, pending, for the
operator before any worker may claim it."""

import argparse
import os
import unittest

from ballotreels.site.config import load_config

from .test_serve_private import ServerTestCaseWithConfig

PROP_90 = "ca-2026-11-03-prop-90"
PROP_91 = "ca-2026-11-03-prop-91"
PROP_92 = "ca-2026-11-03-prop-92"


class ApprovalTestCase(ServerTestCaseWithConfig):
    config_overrides = {"require_approval": True}

    def _request(self, contest, ip=None):
        headers = {"X-Forwarded-For": ip} if ip else None
        return self._public("POST", "/api/generate", {"contest": contest},
                            headers=headers)

    def _claim(self):
        status, body, _ = self._private("POST", "/worker/claim",
                                        {"worker": "w1"})
        return status, body


class PendingTest(ApprovalTestCase):
    def test_request_is_pending_and_not_claimable(self):
        status, body, _ = self._request(PROP_90)
        self.assertEqual(status, 201)
        self.assertEqual(body["job"]["state"], "pending")
        self.assertNotIn("eta_minutes", body["job"])
        self.assertEqual(self._claim()[0], 204)

    def test_apis_report_pending(self):
        job_id = self._request(PROP_90)[1]["job"]["id"]
        status, body, _ = self._public("GET", f"/api/jobs/{job_id}")
        self.assertEqual(body["state"], "pending")
        status, body, _ = self._public("GET", f"/api/contest/{PROP_90}")
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["job"]["state"], "pending")
        status, body, _ = self._public(
            "GET", "/api/ballot?d=ocd-division/country:us/state:ca")
        statewide = {c["id"]: c for lvl in body["levels"]
                     for c in lvl["contests"]}
        self.assertEqual(statewide[PROP_90]["status"], "pending")

    def test_second_request_joins(self):
        first = self._request(PROP_90)[1]["job"]["id"]
        status, body, _ = self._request(PROP_90)
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["id"], first)
        self.assertEqual(len(self.deps.queue.list_jobs()), 1)


class AdminActionsTest(ApprovalTestCase):
    def test_approve_queues_it(self):
        job_id = self._request(PROP_90)[1]["job"]["id"]
        before = self.deps.queue.get_job(job_id)["queued_at"]
        status, _, _ = self._private("POST",
                                     f"/admin/api/jobs/{job_id}/approve")
        self.assertEqual(status, 200)
        job = self.deps.queue.get_job(job_id)
        self.assertEqual(job["state"], "queued")
        self.assertGreaterEqual(job["queued_at"], before)
        status, body = self._claim()
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["id"], job_id)

    def test_reject_cancels_and_stays_rejected(self):
        job_id = self._request(PROP_90)[1]["job"]["id"]
        status, _, _ = self._private("POST",
                                     f"/admin/api/jobs/{job_id}/reject")
        self.assertEqual(status, 200)
        self.assertEqual(self.deps.queue.get_job(job_id)["state"],
                         "cancelled")
        status, body, _ = self._request(PROP_90)
        self.assertEqual(status, 409)
        self.assertEqual(body["status"], "cancelled")

    def test_approve_reject_only_pending(self):
        job_id = self._request(PROP_90)[1]["job"]["id"]
        self._private("POST", f"/admin/api/jobs/{job_id}/approve")
        for action in ("approve", "reject"):
            with self.subTest(action):
                status, _, _ = self._private(
                    "POST", f"/admin/api/jobs/{job_id}/{action}")
                self.assertEqual(status, 409)

    def test_admin_retry_and_regenerate_skip_approval(self):
        job_id = self._request(PROP_90)[1]["job"]["id"]
        self._private("POST", f"/admin/api/jobs/{job_id}/reject")
        self._private("POST", f"/admin/api/jobs/{job_id}/retry")
        self.assertEqual(self.deps.queue.get_job(job_id)["state"], "queued")

        claim = self.deps.queue.claim("w1")["claim"]
        self.deps.queue.complete(job_id, claim)
        self._private("POST", f"/admin/api/jobs/{job_id}/regenerate")
        states = [j["state"] for j in self.deps.queue.list_jobs()]
        self.assertEqual(states, ["done", "queued"])

    def test_monitor_lists_pending_first(self):
        first = self._request(PROP_90)[1]["job"]["id"]
        self._private("POST", f"/admin/api/jobs/{first}/approve")
        second = self._request(PROP_91)[1]["job"]["id"]
        status, body, _ = self._private("GET", "/admin/api/jobs")
        self.assertEqual([j["id"] for j in body["jobs"]], [second, first])
        self.assertEqual(body["pending"], 1)
        self.assertEqual(body["depth"], 1)


class PendingCountsTowardCapTest(ApprovalTestCase):
    config_overrides = {"require_approval": True, "generate_limit": 5,
                        "generate_global_limit": 2,
                        "trust_forwarded_for": True}

    def test_global_cap_counts_pending(self):
        statuses = [self._request(c, ip)[0] for c, ip in (
            (PROP_90, "2001:db8::1"), (PROP_91, "2001:db8::2"),
            (PROP_92, "2001:db8::3"))]
        self.assertEqual(statuses, [201, 201, 429])


class ApprovalOffTest(ApprovalTestCase):
    config_overrides = {"require_approval": False}

    def test_requests_queue_directly(self):
        status, body, _ = self._request(PROP_90)
        self.assertEqual(body["job"]["state"], "queued")
        self.assertEqual(self._claim()[0], 200)


class ApprovalConfigTest(unittest.TestCase):
    def _ns(self, flag):
        return argparse.Namespace(
            data_dir=None, election=None, public_host=None,
            public_port=None, private_host=None, private_port=None,
            generate_limit=None, generate_window=None,
            trust_forwarded_for=None, heartbeat_timeout=None,
            eta_default_minutes=None, max_upload_mb=None,
            require_approval=flag)

    def test_on_by_default_flag_and_env_turn_it_off(self):
        old = os.environ.pop("BALLOTREELS_REQUIRE_APPROVAL", None)
        try:
            self.assertTrue(load_config(self._ns(None)).require_approval)
            self.assertFalse(load_config(self._ns(False)).require_approval)
            os.environ["BALLOTREELS_REQUIRE_APPROVAL"] = "0"
            self.assertFalse(load_config(self._ns(None)).require_approval)
            self.assertTrue(load_config(self._ns(True)).require_approval)
        finally:
            os.environ.pop("BALLOTREELS_REQUIRE_APPROVAL", None)
            if old is not None:
                os.environ["BALLOTREELS_REQUIRE_APPROVAL"] = old


if __name__ == "__main__":
    unittest.main()
