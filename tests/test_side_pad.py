"""narration.side_pad/padded_spans, storyboard.layout's use of them, and
film/measure.py's padded audio: the two side sections end up exactly the
same length on screen (STANDARD.md rule 2.2), by padding the shorter
side's spoken audio with trailing silence."""

import unittest

from ballotreels.contest import load_contest
from ballotreels.narration import match_phrases, padded_spans, side_pad
from ballotreels.storyboard import layout

from .helpers import PROP_2, ContestCopyTestCase, write_narration


class SidePadTest(ContestCopyTestCase):
    def test_no_pad_when_sides_are_equal(self):
        write_narration(self.dir)
        self.assertIsNone(side_pad(load_contest(self.dir)))

    def test_pads_the_shorter_side(self):
        write_narration(self.dir, stretch={"no": 0.97})
        pad = side_pad(load_contest(self.dir))
        self.assertEqual(pad.side, "no")
        self.assertAlmostEqual(pad.seconds, 0.95, delta=0.05)
        self.assertAlmostEqual(pad.at, 236.8, delta=0.05)

    def test_padded_spans_shift_only_what_follows_the_pad(self):
        write_narration(self.dir, stretch={"no": 0.97})
        contest = load_contest(self.dir)
        pad = side_pad(contest)
        raw = {(s.section, s.index): s for s in match_phrases(contest)}
        for s in padded_spans(contest):
            r = raw[(s.section, s.index)]
            shift = pad.seconds if r.start > pad.at else 0.0
            self.assertAlmostEqual(s.start, r.start + shift, places=6)
            self.assertAlmostEqual(s.end, r.end + shift, places=6)

    def test_over_the_cap_pad_is_still_computed(self):
        # narration.side_pad has no opinion on SIDE_PAD_CAP: that is
        # check_airtime's job, since the renderer must lay out something
        # even for a script with a real imbalance.
        write_narration(self.dir, stretch={"no": 0.9})
        pad = side_pad(load_contest(self.dir))
        self.assertGreater(pad.seconds, 2.0)


class LayoutPadTest(ContestCopyTestCase):
    def test_side_sections_match_to_the_frame(self):
        write_narration(self.dir, stretch={"no": 0.97})
        contest = load_contest(self.dir)
        board = layout(contest, 0.0)
        by_side = {sb.section.side: sb for sb in board.sections
                  if sb.section.side is not None}
        a, b = by_side.values()
        self.assertEqual(a.end - a.start, b.end - b.start)

    def test_side_sections_match_to_the_frame_whatever_the_stretch(self):
        # the pad is sized in whole frames from the unpadded layout, so no
        # stretch leaves the two a frame apart from rounding each boundary
        for stretch in (0.97, 0.985, 0.991, 0.996, 1.004, 1.013):
            with self.subTest(stretch=stretch):
                write_narration(self.dir, stretch={"no": stretch})
                board = layout(load_contest(self.dir), 0.0)
                a, b = (sb for sb in board.sections
                        if sb.section.side is not None)
                self.assertEqual(a.end - a.start, b.end - b.start)

    def test_narration_end_follows_the_padded_audio(self):
        # `seconds` is the narration file's own length, before the pad;
        # layout() adds the pad's length on top, so narration_end tracks
        # the audio film/measure.py actually plays, not the raw file.
        write_narration(self.dir, stretch={"no": 0.97})
        contest = load_contest(self.dir)
        pad = side_pad(contest)
        board = layout(contest, 50.0)
        from ballotreels.storyboard import END_HOLD, frame
        self.assertEqual(board.narration_end,
                         frame(50.0 + pad.seconds) + frame(END_HOLD))


class CommittedProp2Test(unittest.TestCase):
    """The real, committed Prop 2 narration: sides 1.4s apart, inside the
    2s cap, so it is padded rather than failing."""

    def test_pad_is_within_the_cap(self):
        pad = side_pad(load_contest(PROP_2))
        self.assertAlmostEqual(pad.seconds, 1.4, delta=0.05)

    def test_measure_pads_the_playing_audio_by_exactly_the_pad(self):
        from film import measure as m
        self.assertIsNotNone(m.PAD)
        sounds = m.voice_sounds()
        self.assertEqual(len(sounds), 2)
        span = max(s.at + s.frames for s in sounds) - min(s.at for s in sounds)
        self.assertEqual(span, m.VOICE.frames(m.FPS) + m.to_frame(m.PAD.seconds, m.FPS))

    def test_measure_sides_match_to_the_frame(self):
        from film import measure as m
        by_side = {sb.section.side: sb for sb in m.BOARD.sections
                  if sb.section.side is not None}
        a, b = by_side.values()
        self.assertEqual(a.end - a.start, b.end - b.start)


if __name__ == "__main__":
    unittest.main()
