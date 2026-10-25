"""narration_text's playback order and the phrase<->line mapping."""

import unittest

from ballotreels.contest import load_contest
from ballotreels.narration import (NarrationError, match_phrases,
                                   narration_text, section_order,
                                   side_durations)

from .helpers import (PROP_2, ContestCopyTestCase, drop_background,
                      write_narration)


class NarrationTextTest(unittest.TestCase):
    def test_one_line_per_script_line_in_playback_order(self):
        contest = load_contest(PROP_2)
        by_label = dict(contest.script.labelled())
        want = [line.text for label in section_order(contest)
                for line in by_label[label].lines]
        self.assertEqual(narration_text(contest).splitlines(), want)
        self.assertEqual(len(want), 37)

    def test_background_plays_between_what_and_today(self):
        lines = narration_text(load_contest(PROP_2)).splitlines()
        self.assertTrue(lines[1].startswith("The Legislature put it"))
        self.assertTrue(lines[2].startswith("Each year, the state spends"))
        self.assertTrue(lines[13].startswith("In 2014, voters approved"))
        self.assertTrue(lines[14].startswith("Each year, the state must put"))

    def test_side_order_matches_narration_order(self):
        # ca-2026-11-03-prop-2 hashes to ("no", "yes"): "no" plays first.
        contest = load_contest(PROP_2)
        self.assertEqual(section_order(contest),
                         ("what", "background[0]", "background[1]",
                          "background[2]", "background[3]", "today",
                          "change", "fiscal", "no", "yes", "vote"))


class BackgroundOrderTest(ContestCopyTestCase):
    def test_background_plays_in_file_order(self):
        path = self.dir / "script.toml"
        chunks = path.read_text(encoding="utf-8").split("[[section]]\n")
        self.assertIn('heading = "Why it swings"', chunks[3])
        self.assertIn('heading = "How we got here"', chunks[5])
        chunks[3], chunks[5] = chunks[5], chunks[3]
        path.write_text("[[section]]\n".join(chunks), encoding="utf-8")
        lines = narration_text(load_contest(self.dir)).splitlines()
        self.assertTrue(lines[5].startswith("Before 1980"))
        self.assertTrue(lines[7].startswith("A reserve fills that gap"))
        self.assertTrue(lines[10].startswith("Those gains rise and fall"))
        self.assertTrue(lines[13].startswith("But the cost of schools"))
        self.assertTrue(lines[14].startswith("Each year, the state must put"))


class MatchPhrasesTest(ContestCopyTestCase):
    def setUp(self):
        super().setUp()
        write_narration(self.dir)

    def test_spans_cover_the_whole_narration(self):
        contest = load_contest(self.dir)
        spans = match_phrases(contest)
        self.assertEqual(len(spans), 37)  # one per script line
        self.assertEqual(spans[0].section, "what")
        self.assertEqual(spans[2].section, "background[0]")
        self.assertEqual(spans[-1].section, "vote")
        # consecutive spans don't go backwards
        for a, b in zip(spans, spans[1:]):
            self.assertLessEqual(a.end, b.start)

    def test_side_durations(self):
        contest = load_contest(self.dir)
        durations = dict(side_durations(contest))
        self.assertEqual(set(durations), {"yes", "no"})
        # 79 words at 0.4s plus three 0.25s gaps between four lines.
        self.assertAlmostEqual(durations["yes"], 32.35, delta=0.02)
        self.assertAlmostEqual(durations["no"], 32.35, delta=0.02)

    def test_match_phrases_raises_on_text_mismatch(self):
        self.edit("script.toml", "The Legislature put it",
                  "The Legislature, somehow, put it")
        with self.assertRaises(NarrationError):
            match_phrases(load_contest(self.dir))

    def test_match_phrases_raises_on_extra_phrases(self):
        drop_background(self.dir)
        with self.assertRaises(NarrationError):
            match_phrases(load_contest(self.dir))


class NoNarrationTest(unittest.TestCase):
    def test_no_sidecars_is_none(self):
        # The committed contest has no narration: it is made on the host.
        contest = load_contest(PROP_2)
        self.assertFalse((PROP_2 / "narration.json").exists())
        self.assertIsNone(match_phrases(contest))
        self.assertIsNone(side_durations(contest))


if __name__ == "__main__":
    unittest.main()
