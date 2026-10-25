"""The measure film's timeline, laid out from the narration."""

import json
import unittest

from ballotreels.contest import load_contest
from ballotreels.narration import (NarrationError, match_phrases,
                                   section_order)
from ballotreels.storyboard import (MIN_CHART, cited_sources, frame, layout,
                                    sources_card_seconds)

from .helpers import PROP_2, ContestCopyTestCase, write_narration


def narration_seconds(contest_dir):
    doc = json.loads((contest_dir / "narration.json").read_text())
    return doc["seconds"]


class StandInLayoutTest(ContestCopyTestCase):
    def setUp(self):
        super().setUp()
        write_narration(self.dir)
        self.contest = load_contest(self.dir)
        self.board = layout(self.contest, narration_seconds(self.dir))

    def test_sections_in_playback_order_without_gaps(self):
        b = self.board
        self.assertEqual(tuple(s.label for s in b.sections),
                         section_order(self.contest))
        self.assertEqual(b.sections[0].start, 0)
        for a, c in zip(b.sections, b.sections[1:]):
            self.assertEqual(a.end, c.start)
        self.assertEqual(b.sections[-1].end, b.narration_end)
        self.assertEqual([s.number for s in b.sections],
                         list(range(len(b.sections))))

    def test_lines_tile_their_section(self):
        for s in self.board.sections:
            self.assertEqual(len(s.lines), len(s.section.lines))
            self.assertEqual(s.lines[0].start, s.start)
            self.assertEqual(s.lines[-1].end, s.end)
            for a, c in zip(s.lines, s.lines[1:]):
                self.assertEqual(a.end, c.start)
                self.assertLess(a.start, a.end)

    def test_a_line_starts_on_its_first_word(self):
        spans = {(p.section, p.index): p for p in match_phrases(self.contest)}
        for s in self.board.sections:
            for b in s.lines[1:]:
                self.assertEqual(b.start,
                                 frame(spans[(s.label, b.index)].start))

    def test_a_page_starts_in_the_pause_before_its_first_word(self):
        spans = {(p.section, p.index): p for p in match_phrases(self.contest)}
        for prev, s in zip(self.board.sections, self.board.sections[1:]):
            first_word = spans[(s.label, 0)].start
            last_word = spans[(prev.label, len(prev.lines) - 1)].end
            self.assertLessEqual(s.start, frame(first_word))
            self.assertGreaterEqual(s.start, frame(last_word))

    def test_charts_show_while_their_line_is_narrated(self):
        charts = self.board.charts
        self.assertEqual([(c.section, c.index, c.visual.kind) for c in charts],
                         [("background[0]", 1, "share"),
                          ("background[1]", 3, "figure"),
                          ("change", 0, "bars")])
        for c in charts:
            sec = next(s for s in self.board.sections if s.label == c.section)
            line = sec.lines[c.index]
            self.assertEqual(c.start, line.start)
            # its line, held to a line's end MIN_CHART on, within the section
            self.assertGreaterEqual(c.end, line.end)
            self.assertIn(c.end, [ln.end for ln in sec.lines])
            held = [ln for ln in sec.lines[c.index:] if ln.end < c.end]
            for ln in held:
                self.assertLess(ln.end, line.start + frame(MIN_CHART))
            self.assertEqual(c.source.id, c.visual.source)

    def test_two_charts_in_a_section_hand_over(self):
        self.edit("script.toml",
                  'sources = ["lao-analysis"]\n\n[[section.line]]\n'
                  'text = "It extends the extra debt',
                  'sources = ["lao-analysis"]\n\n[section.line.visual]\n'
                  'kind = "bars"\ntitle = "T"\nsource = "lao-analysis"\n'
                  'unit = ""\nlabels = ["A", "B"]\nvalues = [1, 1]\n\n'
                  '[[section.line]]\ntext = "It extends the extra debt')
        board = layout(load_contest(self.dir), narration_seconds(self.dir))
        first, second = [c for c in board.charts if c.section == "change"]
        self.assertLessEqual(first.end, second.start)
        self.assertEqual(second.index, 1)

    def test_sources_card_follows_the_narration(self):
        b = self.board
        self.assertEqual(b.narration_end,
                         frame(narration_seconds(self.dir)) + frame(0.5))
        self.assertEqual(b.end - b.narration_end,
                         frame(sources_card_seconds(b.cited)))
        self.assertIsNone(b.section_at(b.narration_end))
        self.assertEqual(b.section_at(0).label, "what")

    def test_no_sidecars(self):
        (self.dir / "narration.json").unlink()
        with self.assertRaises(NarrationError):
            layout(load_contest(self.dir), 10.0)


class CitedSourcesTest(unittest.TestCase):
    def test_uncited_sources_are_left_off_the_card(self):
        cited = [s.id for s in cited_sources(load_contest(PROP_2))]
        self.assertEqual(cited, ["title-summary", "lao-analysis", "arguments",
                                 "quick-reference", "guide-section",
                                 "lao-volatility"])

    def test_card_read_time(self):
        cited = cited_sources(load_contest(PROP_2))
        words = 1 + sum(len(s.publisher.split()) for s in cited)
        self.assertAlmostEqual(sources_card_seconds(cited), 1 + words / 3)


class Prop2LayoutTest(unittest.TestCase):
    def test_real_narration(self):
        board = layout(load_contest(PROP_2), narration_seconds(PROP_2))
        self.assertEqual(len(board.lines), 37)
        self.assertEqual(board.sections[0].start, 0)
        self.assertGreater(board.end, board.narration_end)


if __name__ == "__main__":
    unittest.main()
