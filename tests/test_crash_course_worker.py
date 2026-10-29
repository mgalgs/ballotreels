"""A crash course queued like any contest (POST /api/generate, approved by
the operator), worked by the pull worker from committed data alone, and
shown at the top of its state's page."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import ballotreels.site.config as site_config
from ballotreels.index import key_for
from ballotreels.pipeline import STAGES, FakeRunner, HandWrittenScriptWriter
from ballotreels.queue import hash_for_key
from ballotreels.site.server import build_deps, make_servers
from ballotreels.storage import LocalStorage
from ballotreels.worker import Worker, WorkerClient

from .helpers import copy_election, git_commit_all
from .test_crash_course import UT, edit_vote_line
from .test_serve_public import _make_config

CC_ID = "ut-2026-11-03-crash-course"


class NeverNarrates(FakeRunner):
    def narrate(self, contest_dir):
        raise AssertionError("a crash course asked for a narration")


def refuse_tts(*a, **kw):
    raise AssertionError("the crash course asked the TTS")


class CrashCourseServeTestCase(unittest.TestCase):
    config_overrides: dict = {}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        # one checkout for both tiers, as when they run the same commit
        self.repo = self.tmp / "repo"
        self.election = self.repo / "data" / UT.name
        copy_election(UT, self.election)
        self._old_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = self.repo / "data"
        self.addCleanup(self._restore_root)

        self.config = _make_config(self.tmp / "var", election=UT.name,
                                   **self.config_overrides)
        self.deps = build_deps(self.config)
        self.public, self.private = make_servers(self.deps)
        self.addCleanup(self.deps.queue.close)
        for srv in (self.public, self.private):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(self._shutdown)
        self.client = WorkerClient(
            f"http://127.0.0.1:{self.private.server_address[1]}",
            "test-token")

    def _restore_root(self):
        site_config.DATA_ROOT = self._old_root

    def _shutdown(self):
        for srv in (self.public, self.private):
            srv.shutdown()
            srv.server_close()

    def make_worker(self, runner=None, repo=None):
        # it renders committed HEAD: commit the checkout as the test left it
        git_commit_all(repo or self.repo)
        return Worker(client=self.client, worker_id="w1",
                      repo=repo or self.repo,
                      runner=runner or NeverNarrates(),
                      writer=HandWrittenScriptWriter(),
                      storage=LocalStorage(self.client),
                      standard=self.deps.standard,
                      work_dir=self.tmp / "work",
                      masters_dir=self.tmp / "masters",
                      poll_interval=0.05, heartbeat_interval=0.2)

    def key(self):
        index = self.deps.states["ut"].index
        return key_for(index.election.id, index.crash_course,
                       self.deps.standard)

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.public.server_address[1], timeout=10)
        data = None if body is None else json.dumps(body)
        headers = {} if body is None else {"Content-Type": "application/json"}
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp.status, (json.loads(raw) if raw else None)

    def generate(self, contest_id=CC_ID):
        return self.request("POST", "/api/generate", {"contest": contest_id})


class QueuedLikeAnyContestTest(CrashCourseServeTestCase):
    config_overrides = {"require_approval": True}

    def test_generate_approve_work_and_shown_on_the_state_page(self):
        status, body = self.request("GET", "/api/state/ut")
        self.assertEqual(status, 200)
        self.assertEqual(body["crash_course"]["id"], CC_ID)
        self.assertEqual(body["crash_course"]["status"], "none")
        self.assertIsNone(body["crash_course"]["video_url"])
        # the page's list of measures is as it was
        self.assertEqual([c["id"] for c in body["levels"][0]["contests"]],
                         ["ut-2026-11-03-amendment-a",
                          "ut-2026-11-03-amendment-b"])

        status, body = self.generate()
        self.assertEqual(status, 201)
        self.assertEqual(body["job"]["state"], "pending")
        ok, err = self.deps.queue.transition(body["job"]["id"], "approve")
        self.assertTrue(ok, err)

        from videobuilder import speech
        with mock.patch.object(speech, "say", refuse_tts), \
                mock.patch.object(speech, "Gemini", refuse_tts):
            self.assertTrue(self.make_worker().run_once())
        job = self.deps.queue.get_job(body["job"]["id"])
        self.assertEqual(job["state"], "done", job["error"])
        events = self.deps.queue.stage_events_for(job["id"])
        self.assertEqual({e["stage"] for e in events
                          if e["event"] == "finish"}, set(STAGES) | {"cache"})

        status, body = self.request("GET", "/api/state/ut")
        cc = body["crash_course"]
        self.assertEqual(cc["status"], "cached")
        key_hash = hash_for_key(self.key())
        self.assertEqual(cc["video_url"],
                         f"/v/{key_hash}/{job['id']}/video.mp4")
        index = self.deps.states["ut"].index
        self.assertEqual([c["title"] for c in cc["chapters"]],
                         [index.get(m).title
                          for m in index.crash_course.members])
        self.assertEqual({s["contest"] for s in cc["sources"]},
                         set(index.crash_course.members))
        # its published record quotes the reused lines
        record = (self.config.data_dir / "cache" / key_hash /
                  str(job["id"]) / "script.toml").read_text(encoding="utf-8")
        self.assertIn('contest = "ut-2026-11-03-crash-course"', record)

        # a second request is served from the cache
        status, body = self.generate()
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "cached")

    def test_a_member_change_is_a_new_key_and_hides_the_old_video(self):
        self.deps.queue.record_video(self.key(), "local",
                                     {"video": "/v/x/1/video.mp4"}, [])
        _, body = self.request("GET", "/api/state/ut")
        self.assertEqual(body["crash_course"]["status"], "cached")
        edit_vote_line(self.election / "amendment-a")
        _, body = self.request("GET", "/api/state/ut")
        self.assertEqual(body["crash_course"]["status"], "none")
        self.assertIsNone(body["crash_course"]["video_url"])


class RateLimitTest(CrashCourseServeTestCase):
    config_overrides = {"generate_limit": 1}

    def test_counts_against_the_per_ip_limit_like_any_contest(self):
        status, _ = self.generate("ut-2026-11-03-amendment-a")
        self.assertEqual(status, 201)
        status, _ = self.generate()
        self.assertEqual(status, 429)

    def test_and_the_other_way_round(self):
        status, _ = self.generate()
        self.assertEqual(status, 201)
        status, _ = self.generate("ut-2026-11-03-amendment-b")
        self.assertEqual(status, 429)
        # joining its live job is never limited
        status, body = self.generate()
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["state"], "queued")


class FailsTest(CrashCourseServeTestCase):
    def run_job(self, before_work=None):
        job, _ = self.deps.queue.create_job(self.key())
        if before_work:
            before_work()
        self.assertTrue(self.make_worker().run_once())
        return self.deps.queue.get_job(job["id"])

    def test_a_stale_member_fails_naming_it(self):
        # changed on the one checkout both tiers share: the job is for
        # exactly this data, whose amendment B narration is now stale
        edit_vote_line(self.election / "amendment-b")
        job = self.run_job()
        self.assertEqual(job["state"], "failed")
        self.assertIn("Constitutional Amendment B", job["error"])
        self.assertIn("ut-2026-11-03-amendment-b", job["error"])
        self.assertNotIn("amendment-a", job["error"])

    def test_a_missing_member_narration_fails_naming_it(self):
        for name in ("narration.json", "narration.wav"):
            (self.election / "amendment-a" / name).unlink()
        job = self.run_job()
        self.assertEqual(job["state"], "failed")
        # before the checks that a narrated script skips can confuse it
        self.assertEqual(job["failed_stage"], "check")
        self.assertIn("Constitutional Amendment A", job["error"])
        self.assertIn("no committed narration", job["error"])

    def test_a_worker_whose_measures_differ_from_the_job_s_fails(self):
        job = self.run_job(
            before_work=lambda: edit_vote_line(self.election / "amendment-a"))
        self.assertEqual(job["state"], "failed")
        self.assertEqual(job["failed_stage"], "script")
        self.assertIn("not the one the job was queued for", job["error"])


class TakesFromTheStoreTest(CrashCourseServeTestCase):
    """Each member's narration audio comes from the narration store, by
    the take its narration.json records, as a single measure's does."""

    def setUp(self):
        super().setUp()
        from ballotreels.narration_store import hash_file, record
        self.shas = {}
        for name in ("amendment-a", "amendment-b"):
            d = self.election / name
            record(d)
            wav = d / "narration.wav"
            self.shas[name] = hash_file(wav).sha256
            self.client.narration_put(self.shas[name], wav.read_bytes())
            wav.unlink()

    def run_job(self):
        job, _ = self.deps.queue.create_job(self.key())
        self.assertTrue(self.make_worker().run_once())
        return self.deps.queue.get_job(job["id"])

    def test_renders_from_the_store(self):
        job = self.run_job()
        self.assertEqual(job["state"], "done", job["error"])

    def test_a_member_take_not_in_the_store_fails_naming_it(self):
        sha = self.shas["amendment-a"]
        (self.tmp / "var" / "narration" / f"{sha}.wav").unlink()
        job = self.run_job()
        self.assertEqual(job["state"], "failed")
        self.assertIn("ut-2026-11-03-amendment-a", job["error"])
        self.assertIn(sha, job["error"])


if __name__ == "__main__":
    unittest.main()
