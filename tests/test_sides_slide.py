"""film/measure.py's combined sides slide: both side sections share one
slide, in two congruent blocks (STANDARD.md rule 7.4), instead of each
getting its own page."""

import unittest

from ballotreels.contest import Line, Section, Source, Visual
from ballotreels.storyboard import ChartBeat, LineBeat, SectionBeat

from film import measure as m

SOURCE = Source(id="arguments", kind="official-argument", publisher="Pub",
                url="https://example.com", file="sources/a.html",
                retrieved="2026-01-01")


def _side_section(label, heading, side, start=100, end=300, with_list=True):
    """A minimal SectionBeat for a side section, with or without a 'list'
    visual, for testing side_block/sides_group without a whole contest."""
    items = ["Point one, stated plainly", "Point two, stated plainly"]
    visual = Visual(kind="list", source="arguments", items=items) if with_list else None
    line = Line(text="Some say things about it.", sources=("arguments",),
               connective=False, visual=visual)
    lb = LineBeat(label, 0, line, start, end)
    charts = (ChartBeat(label, 0, visual, SOURCE, start, end),) if with_list else ()
    section = Section(id=label, heading=heading, side=side, lines=(line,))
    return SectionBeat(label, section, 3, start, end, (lb,), charts)


class SideBoxesTest(unittest.TestCase):
    def test_congruent_and_fit_the_stage(self):
        for fmt in ("9x16", "16x9"):
            L = m.LAYOUTS[fmt]
            a, b = m.side_boxes(L, fmt)
            self.assertAlmostEqual(a.w, b.w)
            self.assertAlmostEqual(a.h, b.h)
            st = L["stage"]
            for box in (a, b):
                self.assertGreaterEqual(box.x, st.x - 1e-6)
                self.assertGreaterEqual(box.y, st.y - 1e-6)
                self.assertLessEqual(box.right, st.right + 1e-6)
                self.assertLessEqual(box.bottom, st.bottom + 1e-6)

    def test_9x16_stacks_top_to_bottom(self):
        L = m.LAYOUTS["9x16"]
        a, b = m.side_boxes(L, "9x16")
        self.assertAlmostEqual(a.x, b.x)
        self.assertLess(a.y, b.y)

    def test_16x9_splits_left_to_right(self):
        L = m.LAYOUTS["16x9"]
        a, b = m.side_boxes(L, "16x9")
        self.assertAlmostEqual(a.y, b.y)
        self.assertLess(a.x, b.x)


class SideBlockTest(unittest.TestCase):
    def test_no_list_is_just_the_label(self):
        L = m.LAYOUTS["9x16"]
        box, _ = m.side_boxes(L, "9x16")
        sec = _side_section("no", "Why some vote no", "no", with_list=False)
        items, marks = m.side_block(sec, L, box, 104)
        self.assertTrue(items)  # the label's own strokes
        self.assertEqual([mk.name for mk in marks], ["heading"])

    def test_with_a_list_adds_its_checklist_and_source(self):
        L = m.LAYOUTS["9x16"]
        box, _ = m.side_boxes(L, "9x16")
        sec = _side_section("yes", "Why some vote yes", "yes")
        items, marks = m.side_block(sec, L, box, 104)
        self.assertEqual(sorted(mk.name for mk in marks),
                         ["chart", "chart source", "heading"])
        self.assertGreater(len(items), 2)  # label + 2 check marks + text

    def test_identical_content_in_congruent_boxes_draws_the_same_shape(self):
        # STANDARD.md rule 7.4: nothing about the two blocks may differ
        # but their words and order. With the same words, the two blocks'
        # drawn shapes (not positions) must come out identical.
        L = m.LAYOUTS["9x16"]
        box_a, box_b = m.side_boxes(L, "9x16")
        sec_a = _side_section("no", "Why some vote no", "no")
        sec_b = _side_section("yes", "Why some vote no", "no")  # same heading
        _, marks_a = m.side_block(sec_a, L, box_a, 104)
        _, marks_b = m.side_block(sec_b, L, box_b, 104)
        by_name_a = {mk.name: mk.box for mk in marks_a}
        by_name_b = {mk.name: mk.box for mk in marks_b}
        self.assertEqual(set(by_name_a), set(by_name_b))
        for name in by_name_a:
            self.assertAlmostEqual(by_name_a[name].w, by_name_b[name].w, places=3)
            self.assertAlmostEqual(by_name_a[name].h, by_name_b[name].h, places=3)


class SidesGroupTest(unittest.TestCase):
    def test_fixed_heading_plus_one_label_per_side(self):
        L = m.LAYOUTS["9x16"]
        side_a = _side_section("no", "Why some vote no", "no", 100, 300)
        side_b = _side_section("yes", "Why some vote yes", "yes", 300, 500)
        items, marks = m.sides_group(side_a, side_b, L, "9x16", 104)
        self.assertTrue(items)
        self.assertEqual(sum(1 for mk in marks if mk.name == "heading"), 3)


class BuildHoldsSidesAsOneTest(unittest.TestCase):
    def test_prop_2_holds_one_group_through_both_sides(self):
        # The real, committed Prop 2 contest has no list on its sides, but
        # build() must still hold one slide through both sections, not one
        # per section.
        side_secs = [sb for sb in m.BOARD.sections if sb.section.side is not None]
        self.assertEqual(len(side_secs), 2)
        side_a, side_b = side_secs
        result = m.build("9x16")
        spanning = [g for g in result["groups"]
                   if side_a.start <= g.f0 < side_b.end]
        self.assertEqual(len(spanning), 1)
        self.assertEqual(spanning[0].f0, side_a.start)
        self.assertEqual(spanning[0].out, side_b.end)


if __name__ == "__main__":
    unittest.main()
