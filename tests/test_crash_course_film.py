"""The crash course film (film/crash_course.py), built for Utah: every
sound it plays is a cut of a member's committed narration (or the soft
drawing sound), made without the TTS; each slot replays its member's own
film; the slot's held end says nothing and shows no caption; and every
frame leads to the state's page."""

import os
import unittest
from pathlib import Path
from unittest import mock

from ballotreels import crash_course as cc

from .test_crash_course import UT


def refuse_tts(*a, **kw):
    raise AssertionError("the crash course film asked the TTS")


class CrashCourseFilmTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import videobuilder as vb
        from videobuilder import speech
        old = os.environ.get("BALLOTREELS_CRASH_COURSE")
        os.environ["BALLOTREELS_CRASH_COURSE"] = str(UT)
        try:
            with mock.patch.object(speech, "say", refuse_tts), \
                    mock.patch.object(speech, "Gemini", refuse_tts), \
                    mock.patch.object(speech, "Kokoro", refuse_tts), \
                    mock.patch.object(speech, "Chatterbox", refuse_tts):
                cls.m = vb.load_module(str(UT.parent.parent / "film" /
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

    def test_the_cuts_are_the_plan_s_inside_their_slots(self):
        voices = self.voices()
        self.assertEqual(len(voices), 2 * len(self.course.members))
        k = 0
        for i, m in enumerate(self.course.members):
            pos = self.course.slot_start(i)
            for p in m.parts:
                s = voices[k]
                k += 1
                self.assertEqual(s.at, pos + p.audio_at)
                self.assertAlmostEqual(s.start, p.audio_from, places=6)
                self.assertEqual(s.frames, p.audio_frames)
                self.assertGreaterEqual(s.at, self.course.slot_start(i))
                self.assertLessEqual(s.at + s.frames,
                                     self.course.slot_start(i + 1))
                pos += p.frames

    def test_its_length_and_chapters(self):
        self.assertEqual(self.m.FILM.frames, self.course.slots_end +
                         self.m.SOURCES_PAGE * len(self.m.PAGES))
        self.assertEqual(self.m.CHAPTERS, cc.chapters(self.course))
        self.assertEqual([f.name for f in self.m.FILM.formats], ["9x16"])

    def test_each_slot_replays_its_member_s_own_film(self):
        for i, m in enumerate(self.course.members):
            a, b = m.parts
            start = self.course.slot_start(i)
            view, n = self.m.at(start)
            self.assertIs(view.mod, self.m.FILMS[i])
            self.assertEqual(n, a.start)
            self.assertEqual(self.m.at(start + a.frames)[1], b.start)
            self.assertEqual(self.m.at(start + m.frames - 1)[1], b.end - 1)
            # held, to the slot's end
            self.assertEqual(self.m.at(self.course.slot_start(i + 1) - 1)[1],
                             b.end - 1)
        self.assertIsNone(self.m.at(0))
        self.assertIsNone(self.m.at(self.course.slots_end))

    def test_the_link_on_every_frame_is_the_state_page(self):
        self.assertEqual(self.m.LINK, "ballotreels.org/ut/2026")
        for mod in self.m.FILMS:
            self.assertEqual(mod.LINK, self.m.LINK)

    def marks(self, n):
        return {name for name, _ in self.m.FILM.frame(n).marks}

    def test_a_caption_while_it_speaks_and_none_in_the_hold(self):
        m = self.course.members[0]
        a = m.parts[0]
        said = self.course.slot_start(0) + round(
            (a.said_from + a.said_to) / 2 * self.course.fps) - a.start
        self.assertIn("caption", self.marks(said))
        self.assertIn("link", self.marks(said))
        # the gap at the slot's end holds its last frame, uncaptioned
        held = self.course.slot_start(1) - 1
        self.assertGreater(held, self.course.slot_start(0) + m.frames - 1)
        self.assertNotIn("caption", self.marks(held))
        # the opening card and the sources card: link and footer, no caption
        for n in (self.course.opening - 1, self.m.FILM.frames - 1):
            got = self.marks(n)
            self.assertIn("link", got)
            self.assertIn("footer", got)
            self.assertNotIn("caption", got)
        self.assertIn("sources", self.marks(self.m.FILM.frames - 1))


if __name__ == "__main__":
    unittest.main()
