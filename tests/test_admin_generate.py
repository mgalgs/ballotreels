"""The operator's /admin/api/generate: the same job /api/generate
makes, behind the admin token and outside the public rate limits."""

import unittest

from .test_serve_private import ServerTestCaseWithConfig

PROP_90 = "ca-2026-11-03-prop-90"
PROP_91 = "ca-2026-11-03-prop-91"
PROP_92 = "ca-2026-11-03-prop-92"

# Fields that differ between any two jobs regardless of who made them.
_PER_JOB = {"id", "queued_at"}


class AdminGenerateTestCase(ServerTestCaseWithConfig):
    config_overrides = {"require_approval": True, "generate_limit": 1,
                        "generate_window": 3600,
                        "generate_global_limit": 1}

    def _public_generate(self, contest):
        return self._public("POST", "/api/generate", {"contest": contest})

    def _admin_generate(self, contest, headers=None):
        return self._private("POST", "/admin/api/generate",
                             {"contest": contest}, headers=headers)


class AdminGenerateTest(AdminGenerateTestCase):
    def test_creates_while_public_is_limited(self):
        self.assertEqual(self._public_generate(PROP_90)[0], 201)
        self.assertEqual(self._public_generate(PROP_91)[0], 429)
        status, body, _ = self._admin_generate(PROP_91)
        self.assertEqual(status, 201)
        self.assertEqual(body["job"]["state"], "pending")
        self.assertEqual(len(self.deps.queue.list_jobs()), 2)

    def test_does_not_use_up_public_limit(self):
        for contest in (PROP_90, PROP_91):
            self.assertEqual(self._admin_generate(contest)[0], 201)
        self.assertEqual(self.deps.rate_hits, {})
        self.assertEqual(self.deps.global_hits, [])
        self.assertEqual(self._public_generate(PROP_92)[0], 201)

    def test_job_matches_public_job(self):
        status, public_body, _ = self._public_generate(PROP_90)
        self.assertEqual(status, 201)
        public = self.deps.queue.get_job(public_body["job"]["id"])
        # Drop it, or the admin request would just join it.
        with self.deps.queue._lock:
            self.deps.queue._conn.execute(
                "DELETE FROM jobs WHERE id = ?", (public["id"],))
        status, admin_body, _ = self._admin_generate(PROP_90)
        self.assertEqual(status, 201)
        admin = self.deps.queue.get_job(admin_body["job"]["id"])
        self.assertNotEqual(admin["id"], public["id"])
        for field in _PER_JOB:
            del public[field], admin[field]
            public_body["job"].pop(field, None)
            admin_body["job"].pop(field, None)
        self.assertEqual(admin, public)
        self.assertEqual(admin_body, public_body)

    def test_unknown_contest_is_404(self):
        status, body, _ = self._admin_generate("no-such-contest")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "no such contest"})


class AdminGenerateAuthTest(AdminGenerateTestCase):
    def test_no_token_is_refused(self):
        status, _, resp = self._admin_generate(
            PROP_90, headers={"Authorization": ""})
        self.assertEqual(status, 401)
        self.assertEqual(resp.getheader("WWW-Authenticate"), "Bearer")
        self.assertEqual(self.deps.queue.list_jobs(), [])

    def test_wrong_token_is_refused(self):
        status, _, _ = self._admin_generate(
            PROP_90, headers={"Authorization": "Bearer wrong-token"})
        self.assertEqual(status, 401)
        self.assertEqual(self.deps.queue.list_jobs(), [])


if __name__ == "__main__":
    unittest.main()
