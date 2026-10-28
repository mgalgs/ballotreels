"""The measure film's timeline, laid out from the narration."""

import json
import unittest

from ballotreels.contest import load_contest
from ballotreels.narration import (NarrationError, match_phrases,
                                   section_order)
from ballotreels.storyboard import (SOURCES_CARD_SECONDS, cited_sources,
                                    frame, layout)

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
            # up until the section ends: no later line brings a visual
            self.assertEqual(c.end, sec.end)
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
        self.assertEqual(first.end, second.start)
        self.assertEqual(second.index, 1)

    def test_illustrations_have_no_source(self):
        self.edit("script.toml", 'until 2030."\nsources = ["lao-analysis"]',
                  'until 2030."\nsources = ["lao-analysis"]\n\n'
                  '[section.line.visual]\nkind = "illustration"\n'
                  'name = "debt-payments"\n')
        board = layout(load_contest(self.dir), narration_seconds(self.dir))
        [w] = [c for c in board.charts if c.visual.kind == "illustration"]
        self.assertIsNone(w.source)
        today = next(s for s in board.sections if s.label == "today")
        self.assertEqual((w.start, w.end),
                         (today.lines[2].start, today.end))

    def test_sources_card_follows_the_narration(self):
        b = self.board
        self.assertEqual(b.narration_end,
                         frame(narration_seconds(self.dir)) + frame(0.5))
        self.assertEqual(b.end - b.narration_end,
                         frame(SOURCES_CARD_SECONDS))
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

    def test_card_holds_five_seconds(self):
        self.assertEqual(SOURCES_CARD_SECONDS, 5.0)


class FrameTest(unittest.TestCase):
    def test_halves_round_up(self):
        self.assertEqual(frame(63.15), 1895)  # 1894.5 frames
        self.assertEqual(frame(0.05), 2)

    def test_a_whole_frame_shift_moves_the_frame_by_exactly_that(self):
        # narration.side_pad pads in whole frames, k / fps seconds, added
        # to centisecond phrase times; each padded boundary has to land
        # exactly k frames later, or a boundary sitting on a half frame
        # (Prop 45's 63.15 s) rounds the other way once padded and hands a
        # frame from one side to the other
        for cs in range(0, 12000, 5):
            t = cs / 100
            for k in range(0, 61):
                with self.subTest(t=t, k=k):
                    self.assertEqual(frame(t + k / 30), frame(t) + k)


class Prop2LayoutTest(unittest.TestCase):
    def test_real_narration(self):
        board = layout(load_contest(PROP_2), narration_seconds(PROP_2))
        self.assertEqual(len(board.lines), 37)
        self.assertEqual(board.sections[0].start, 0)
        self.assertGreater(board.end, board.narration_end)


if __name__ == "__main__":
    unittest.main()
