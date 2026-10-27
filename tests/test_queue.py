import tempfile
import unittest
from pathlib import Path

from ballotreels.queue import JobQueue

KEY = ("ca-2026-11-03", "ocd-division/country:us/state:ca",
      "ca-2026-11-03-prop-90", 2, 2)
KEY2 = ("ca-2026-11-03", "ocd-division/country:us/state:ca",
       "ca-2026-11-03-prop-91", 2, 2)


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.clock = FakeClock()
        self.path = Path(tmp.name) / "queue.sqlite3"
        self.queue = JobQueue(self.path, clock=self.clock)
        self.addCleanup(self.queue.close)


class DedupeTest(QueueTestCase):
    def test_dedupe_queued(self):
        job1, created1 = self.queue.create_job(KEY)
        job2, created2 = self.queue.create_job(KEY)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(job1["id"], job2["id"])

    def test_dedupe_running(self):
        self.queue.create_job(KEY)
        claimed = self.queue.claim("worker-1")
        self.assertEqual(claimed["key"], job_key_string(KEY))
        job2, created2 = self.queue.create_job(KEY)
        self.assertFalse(created2)
        self.assertEqual(job2["id"], claimed["id"])


def job_key_string(key):
    from ballotreels.index import key_string
    return key_string(key)


def _key(contest: str):
    return ("ca-2026-11-03", "ocd-division/country:us/state:ca", contest, 2, 2)


class EtaTest(QueueTestCase):
    def setUp(self):
        super().setUp()
        # Large enough that jumping the fake clock across a job's
        # simulated duration never trips the heartbeat-timeout sweep;
        # that sweep is R-Q3's concern, not this test's.
        self.queue.heartbeat_timeout = 1_000_000.0

    def test_eta(self):
        job1, _ = self.queue.create_job(_key("q1"))
        job2, _ = self.queue.create_job(_key("q2"))
        self.assertEqual(self.queue.eta_minutes(
            self.queue.get_job(job1["id"])), 10)
        self.assertEqual(self.queue.eta_minutes(
            self.queue.get_job(job2["id"])), 20)
        self.queue.transition(job1["id"], "cancel")
        self.queue.transition(job2["id"], "cancel")

        # Three done jobs of 60s, 120s, 300s -> median 120s = 2 min.
        self._finish_job("done-1", 60.0)
        self._finish_job("done-2", 120.0)
        self._finish_job("done-3", 300.0)
        job3, _ = self.queue.create_job(_key("q3"))
        job4, _ = self.queue.create_job(_key("q4"))
        self.assertEqual(self.queue.eta_minutes(
            self.queue.get_job(job3["id"])), 2)
        self.assertEqual(self.queue.eta_minutes(
            self.queue.get_job(job4["id"])), 4)
        self.queue.transition(job3["id"], "cancel")
        self.queue.transition(job4["id"], "cancel")

        # A running job 90s into a 120s median -> 0.5 min, floored to 1.
        self.queue.create_job(_key("running"))
        claimed = self.queue.claim("worker-1")
        self.clock.advance(90.0)
        self.assertEqual(self.queue.eta_minutes(
            self.queue.get_job(claimed["id"])), 1)

        # Past the median entirely -> still floored to 1, not negative.
        self.clock.advance(60.0)
        self.assertEqual(self.queue.eta_minutes(
            self.queue.get_job(claimed["id"])), 1)

    def _finish_job(self, contest: str, duration: float) -> None:
        self.queue.create_job(_key(contest))
        claimed = self.queue.claim("worker-x")
        self.clock.advance(duration)
        self.queue.complete(claimed["id"], claimed["claim"])


class RestartTest(QueueTestCase):
    def test_survives_restart(self):
        job1, _ = self.queue.create_job(KEY)
        job2, _ = self.queue.create_job(KEY2)
        claimed = self.queue.claim("worker-1")
        self.queue.close()

        reopened = JobQueue(self.path, clock=self.clock)
        self.addCleanup(reopened.close)
        jobs = {j["id"]: j for j in reopened.list_jobs()}
        self.assertEqual(set(jobs), {job1["id"], job2["id"]})
        self.assertEqual(jobs[claimed["id"]]["state"], "running")
        other_id = job2["id"] if claimed["id"] == job1["id"] else job1["id"]
        self.assertEqual(jobs[other_id]["state"], "queued")


if __name__ == "__main__":
    unittest.main()
