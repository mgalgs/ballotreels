"""The crash course film (film/crash_course.py), built for California: a
contact sheet of one-liners. Every sound it plays is a cut of a member's
committed narration (or the soft drawing sound), made without the TTS;
each tile is drawn on in its own slot, the same size as every other;
and every frame leads to the state's page."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ballotreels import crash_course as cc
from ballotreels.index import load_index

from .helpers import REPO, copy_election
from .test_crash_course import CA


def refuse_tts(*a, **kw):
    raise AssertionError("the crash course film asked the TTS")


class CrashCourseFilmTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import videobuilder as vb
        from videobuilder import speech
        # its members copied, each with a stand-in for its take
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        index = load_index(CA)
        election = copy_election(CA, Path(tmp.name) / CA.name, contests={
            cc.member_dir(CA, index.election.id, cid).name
            for cid in index.crash_course.members})
        old = os.environ.get("BALLOTREELS_CRASH_COURSE")
        os.environ["BALLOTREELS_CRASH_COURSE"] = str(election)
        try:
            with mock.patch.object(speech, "say", refuse_tts), \
                    mock.patch.object(speech, "Gemini", refuse_tts), \
                    mock.patch.object(speech, "Kokoro", refuse_tts), \
                    mock.patch.object(speech, "Chatterbox", refuse_tts):
                cls.m = vb.load_module(str(REPO / "film" /
                                           "crash_course.py"))
        finally:
            if old is None:
                os.environ.pop("BALLOTREELS_CRASH_COURSE", None)
            else:
                os.environ["BALLOTREELS_CRASH_COURSE"] = old
        cls.course = cls.m.COURSE

    def voices(self):
        return [s for s in self.m.FILM.sounds
                if Path(s.path).name == "narration.wav"]

    def marks(self, n, fmt="9x16"):
        return [name for name, _ in self.m.FILM.frame(n, fmt).marks]

    def test_every_sound_is_a_member_narration_cut_or_the_drawing(self):
        wavs = {str(Path(m.contest.path, "narration.wav").resolve())
                for m in self.course.members}
        for s in self.m.FILM.sounds:
            if Path(s.path).name == "narration.wav":
                self.assertIn(str(Path(s.path).resolve()), wavs)
            else:
                self.assertEqual(Path(s.path).parent.name,
                                 "ballotreels-draw-sound", s)
                self.assertFalse(s.ducks)

    def test_each_cut_is_the_plan_s_at_its_slot(self):
        voices = self.voices()
        self.assertEqual(len(voices), len(self.course.members))
        for i, (m, s) in enumerate(zip(self.course.members, voices)):
            self.assertEqual(Path(s.path).parent.resolve(),
                             Path(m.contest.path).resolve())
            self.assertEqual(s.at, self.course.slot_start(i))
            self.assertAlmostEqual(s.start, m.audio_from, places=6)
            self.assertEqual(s.frames, m.audio_frames)
            self.assertLessEqual(s.at + s.frames,
                                 s.at + self.course.slots[i])
        # nothing is said over the opening card, a page's heading or the
        # closing page
        for s in voices:
            self.assertGreaterEqual(s.at, self.course.opening)
            self.assertLessEqual(s.at + s.frames, self.course.slots_end)

    def test_its_length_and_chapters(self):
        self.assertEqual(self.m.FILM.frames, self.course.sources_start +
                         self.m.SOURCES_PAGE * len(self.m.PAGES))
        self.assertEqual(self.course.closing, 3 * self.course.fps)
        self.assertEqual(self.m.CHAPTERS, cc.chapters(self.course))
        self.assertEqual([f.name for f in self.m.FILM.formats],
                         ["9x16", "16x9"])

    def test_the_link_on_every_frame_is_the_state_page(self):
        self.assertEqual(self.m.LINK, "ballotreels.org/ca/2026")
        self.assertEqual(self.m.T.LINK, self.m.LINK)
        for n in (0, self.course.slot_start(3), self.m.FILM.frames - 1):
            self.assertIn("link", self.marks(n))

    def test_each_tile_shows_its_measure_s_own_video(self):
        m = self.course.members[2]
        self.assertEqual(self.m.tile_url(m), "ballotreels.org/ca/2026/prop-3")
        self.assertEqual(self.m.tile_badge(m), ("PROP", "3"))
        self.assertTrue(self.m.short_title(m).startswith("PROVIDES "))

    def test_tiles_come_on_one_at_a_time_and_stay_on_their_page(self):
        for fmt in self.m.FORMATS:
            for k, page in enumerate(self.course.pages):
                for j, i in enumerate(page):
                    # the slot's last frame: this tile and every one
                    # before it on the page, and no later one
                    n = self.course.slot_start(i) + self.course.slots[i] - 1
                    got = self.marks(n, fmt)
                    self.assertEqual(got.count("tile"), j + 1, (fmt, k, i))
                    self.assertEqual(got.count("tile url"), j + 1)
                    self.assertIn("heading", got)
                    self.assertNotIn("caption", got)
                # the next page comes on clean
                after = self.course.page_start(k + 1) + self.m.T.FADE
                self.assertNotIn("tile", self.marks(after, fmt))

    def test_every_tile_is_the_same_size_in_the_same_type(self):
        for fmt in self.m.FORMATS:
            L = self.m.T.LAYOUTS[fmt]
            sizes = set()
            for k in range(len(self.course.pages)):
                n = self.course.page_start(k + 1) - 1
                cv = self.m.FILM.frame(n, fmt)
                for name, box in cv.marks:
                    if name == "tile":
                        sizes.add((round(box.w, 3), round(box.h, 3)))
                        self.assertGreaterEqual(box.x, 0)
                        self.assertLessEqual(box.x + box.w, L["W"])
                        self.assertLessEqual(box.y + box.h,
                                             dict(cv.marks)["link"].y)
            self.assertEqual(len(sizes), 1, fmt)
        self.assertEqual(self.m.GRIDS, {"9x16": (2, 3), "16x9": (3, 2)})

    def test_each_one_liner_fits_its_tile_verbatim(self):
        from videobuilder import text
        for fmt in self.m.FORMATS:
            L = self.m.T.LAYOUTS[fmt]
            fnt = self.m.VIEWS[fmt]["line_font"]
            box = self.m.cells(L, fmt, self.m.page_head(L, 1, 3, 0)[2])[0]
            for m in self.course.members:
                p = self.m.tile_parts(m, box, L)
                lines = text.wrap(m.line.text, fnt, p["inner"])
                self.assertEqual(" ".join(lines).replace("- ", "-"),
                                 m.line.text.replace("- ", "-"))
                self.assertLessEqual(p["line_top"] + len(lines)
                                     * text.line_height(fnt), p["url_y"])

    def test_the_closing_page_is_still_and_silent(self):
        a, b = self.course.slots_end, self.course.sources_start
        got = self.marks(b - self.m.T.FADE - 1)
        self.assertIn("closing", got)
        self.assertIn("closing link", got)
        self.assertNotIn("tile", got)
        for s in self.voices():
            self.assertFalse(s.at < b and s.at + s.frames > a)

    def test_16x9_cards_fit_the_landscape_frame(self):
        film = self.m.FILM
        W, H = 1920, 1080
        last = [self.course.sources_start + (k + 1) * self.m.SOURCES_PAGE
                - self.m.T.FADE - 1 for k in range(len(self.m.PAGES))]
        pages = [self.course.page_start(k + 1) - 1
                 for k in range(len(self.course.pages))]
        for n in (self.course.opening - self.m.T.FADE - 1, *pages,
                  self.course.sources_start - self.m.T.FADE - 1, *last):
            cv = film.frame(n, "16x9")
            self.assertEqual((cv.width, cv.height), (W, H))
            marks = dict(cv.marks)
            self.assertIn("link", marks)
            for name, box in cv.marks:
                self.assertGreaterEqual(box.x, 0, (n, name))
                self.assertGreaterEqual(box.y, 0, (n, name))
                self.assertLessEqual(box.x + box.w, W, (n, name))
                self.assertLessEqual(box.y + box.h, H, (n, name))
            if n in last:
                # the list ends above the link under it
                self.assertLessEqual(marks["sources"].bottom,
                                     marks["link"].y, n)


if __name__ == "__main__":
    unittest.main()
