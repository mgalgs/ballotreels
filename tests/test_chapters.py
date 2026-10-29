"""Chapters: the render writes each section's start beside the video, the
worker hands them to the serve tier with the finished job, and the
contest API returns them for the page's chapter list. A video rendered
before any of this has none, and its page shows none."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ballotreels.contest import load_contest
from ballotreels.pipeline import (FakeRunner, chapters_path, read_chapters,
                                  write_chapters)
from ballotreels.queue import JobQueue
from ballotreels.site.server import _valid_chapters
from ballotreels.storyboard import chapters, layout
from tests.helpers import PROP_2, film_measure
from tests.test_worker import WorkerTestCase

HEADINGS = ["Proposition 2", "Why a rainy day fund", "Today",
            "What would change", "What the state's analyst says",
            "Why some vote no", "Why some vote yes", "What your vote means"]


class StoryboardChaptersTest(unittest.TestCase):
    def test_one_per_section_at_its_start_with_its_heading(self):
        board = layout(load_contest(PROP_2), 60.0)
        got = chapters(board)
        self.assertEqual([c["title"] for c in got],
                         [s.section.heading for s in board.sections])
        for c, s in zip(got, board.sections):
            # at the section's first frame, never before it
            self.assertGreaterEqual(c["start"] * board.fps, s.start)
            self.assertLess(c["start"] * board.fps, s.start + 0.05)
            self.assertEqual(c["start"], round(c["start"], 3))
        self.assertEqual(got[0]["start"], 0)

    def test_the_film_s_chapters_match_its_sections(self):
        m = film_measure()
        self.assertEqual([c["title"] for c in m.CHAPTERS], HEADINGS)
        # the film's own timeline starts each section there
        starts = {s.name: s.at for s in m.TIMELINE.segments}
        for c, s in zip(m.CHAPTERS, m.BOARD.sections):
            self.assertEqual(int(c["start"] * m.FPS), starts[s.label])


class ChaptersFileTest(unittest.TestCase):
    def test_written_beside_the_video_and_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "ca-2026-11-03-prop-2-9x16.mp4"
            got = [{"start": 0.0, "title": "Proposition 2"},
                   {"start": 3.833, "title": "Why some vote “no”"}]
            path = write_chapters(video, got)
            self.assertEqual(path, chapters_path(video))
            self.assertEqual(path.name,
                             "ca-2026-11-03-prop-2-9x16.chapters.json")
            self.assertEqual(read_chapters(video), got)

    def test_an_older_render_has_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_chapters(Path(tmp) / "x-9x16.mp4"))


class ValidChaptersTest(unittest.TestCase):
    def test_accepts_the_render_s_own(self):
        board = layout(load_contest(PROP_2), 60.0)
        self.assertTrue(_valid_chapters(chapters(board)))
        self.assertTrue(_valid_chapters([]))

    def test_refuses_anything_else(self):
        for bad in ("x", [1], [{"start": 0}], [{"start": "0", "title": "a"}],
                    [{"start": -1, "title": "a"}],
                    [{"start": 2, "title": "a"}, {"start": 1, "title": "b"}],
                    [{"start": 0, "title": " "}],
                    [{"start": True, "title": "a"}],
                    [{"start": 0, "title": "a", "x": 1}],
                    [{"start": 0, "title": "a"}] * 65):
            self.assertFalse(_valid_chapters(bad), bad)


class QueueChaptersTest(unittest.TestCase):
    KEY = ("ca-2026-11-03", "ocd-division/country:us/state:ca",
           "ca-2026-11-03-prop-2", 2, 2)

    def test_a_video_keeps_its_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = JobQueue(Path(tmp) / "q.sqlite3")
            self.addCleanup(q.close)
            q.record_video(self.KEY, "local", {}, [],
                           [{"start": 0.0, "title": "A"}])
            self.assertEqual(q.video_for(self.KEY).chapters,
                             [{"start": 0.0, "title": "A"}])
            q.record_video(self.KEY, "local", {}, [])
            self.assertIsNone(q.video_for(self.KEY).chapters)

    def test_a_queue_from_before_chapters_gains_the_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.sqlite3"
            conn = sqlite3.connect(path)
            conn.executescript(
                "CREATE TABLE videos (key_hash TEXT PRIMARY KEY, key TEXT "
                "NOT NULL, election TEXT NOT NULL, division TEXT NOT NULL, "
                "contest TEXT NOT NULL, standard_version INTEGER NOT NULL, "
                "template_version INTEGER NOT NULL, storage TEXT NOT NULL, "
                "urls TEXT NOT NULL, sources TEXT NOT NULL, "
                "created_at REAL NOT NULL);"
                "INSERT INTO videos VALUES ('h', 'k', 'e', 'd', 'c', 2, 2, "
                "'local', '{}', '[]', 0);")
            conn.commit()
            conn.close()
            q = JobQueue(path)
            self.addCleanup(q.close)
            self.assertIsNone(q.video_for_hash("h").chapters)


class WorkerChaptersTest(WorkerTestCase):
    def contest_api(self):
        resp, body = self.get_public("/api/contest/ca/2026/prop-2")
        self.assertEqual(resp.status, 200)
        return json.loads(body)

    def test_a_finished_job_s_chapters_reach_the_contest_api(self):
        key = self.prop2_key()
        self.deps.queue.create_job(key)
        self.assertTrue(self.make_worker().run_once())
        got = self.contest_api()["chapters"]
        board = layout(load_contest(PROP_2), 60.0)
        self.assertEqual([c["title"] for c in got],
                         [s.section.heading for s in board.sections])
        self.assertEqual(got[0]["start"], 0)
        self.assertEqual(got, sorted(got, key=lambda c: c["start"]))

    def test_a_render_without_chapters_leaves_the_page_without(self):
        class OldRunner(FakeRunner):
            def render(self, contest_dir, out_dir):
                dest = super().render(contest_dir, out_dir)
                chapters_path(dest).unlink()
                return dest

        self.deps.queue.create_job(self.prop2_key())
        self.assertTrue(self.make_worker(runner=OldRunner()).run_once())
        detail = self.contest_api()
        self.assertEqual(detail["status"], "cached")
        self.assertEqual(detail["chapters"], [])

    def test_the_serve_tier_refuses_bad_chapters(self):
        job, _ = self.deps.queue.create_job(self.prop2_key())
        claimed = self.client.claim("w1")
        from ballotreels.worker import WorkerApiError
        with self.assertRaises(WorkerApiError) as e:
            self.client.complete(claimed["id"], claimed["claim"], "s3", [],
                                 objects={"video": {"url": "https://x/v"},
                                          "poster": {"url": "https://x/p"}},
                                 chapters=[{"start": "soon", "title": "A"}])
        self.assertEqual(e.exception.status, 400)


if __name__ == "__main__":
    unittest.main()
