"""narration_text's playback order and the phrase<->line mapping."""

import unittest

from ballotreels.contest import load_contest
from ballotreels.narration import (NarrationError, match_phrases,
                                   narration_text, section_order,
                                   side_durations)

from .helpers import PROP_2, ContestCopyTestCase


class NarrationTextTest(unittest.TestCase):
    def test_matches_committed_file(self):
        contest = load_contest(PROP_2)
        self.assertEqual(narration_text(contest),
                         (PROP_2 / "narration.txt").read_text(encoding="utf-8"))

    def test_side_order_matches_narration_order(self):
        # ca-2026-11-03-prop-2 hashes to ("no", "yes"): "no" plays first.
        contest = load_contest(PROP_2)
        self.assertEqual(section_order(contest),
                         ("what", "background[0]", "background[1]",
                          "background[2]", "background[3]", "today",
                          "change", "fiscal", "no", "yes", "vote"))


class MatchPhrasesTest(unittest.TestCase):
    def test_spans_cover_the_whole_narration(self):
        contest = load_contest(PROP_2)
        spans = match_phrases(contest)
        self.assertEqual(len(spans), 20)  # one per script line
        self.assertEqual(spans[0].section, "what")
        self.assertEqual(spans[-1].section, "vote")
        # consecutive spans don't go backwards
        for a, b in zip(spans, spans[1:]):
            self.assertLessEqual(a.end, b.start)

    def test_side_durations_within_tolerance(self):
        contest = load_contest(PROP_2)
        (side_a, dur_a), (side_b, dur_b) = side_durations(contest)
        self.assertEqual({side_a, side_b}, {"yes", "no"})
        self.assertAlmostEqual(dict([(side_a, dur_a), (side_b, dur_b)])["no"],
                               30.07, delta=0.1)
        self.assertAlmostEqual(dict([(side_a, dur_a), (side_b, dur_b)])["yes"],
                               28.69, delta=0.1)
        self.assertLessEqual(abs(dur_a - dur_b), 0.05 * max(dur_a, dur_b))


class StaleNarrationTest(ContestCopyTestCase):
    def test_match_phrases_raises_on_text_mismatch(self):
        self.edit("script.toml", "The Legislature placed",
                  "The Legislature, somehow, placed")
        contest = load_contest(self.dir)
        with self.assertRaises(NarrationError):
            match_phrases(contest)

    def test_no_sidecars_is_none(self):
        (self.dir / "narration.json").unlink()
        contest = load_contest(self.dir)
        self.assertIsNone(match_phrases(contest))
        self.assertIsNone(side_durations(contest))


if __name__ == "__main__":
    unittest.main()
