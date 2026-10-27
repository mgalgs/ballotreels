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


OTHER = Source(id="other", kind="official-argument", publisher="Other",
               url="https://example.org", file="sources/b.html",
               retrieved="2026-01-01")

LAYOUTS = ("compact", "cards", "halves")
LONG = "Protects schools, health care and public safety in every single downturn ahead"


def _side_section(label, heading, side, start=100, end=300, with_list=True, items=None,
                  source=SOURCE):
    """A minimal SectionBeat for a side section, with or without a 'list'
    visual, for testing side_block/sides_group without a whole contest."""
    items = items or ["Point one, stated plainly", "Point two, stated plainly"]
    visual = Visual(kind="list", source=source.id, items=items) if with_list else None
    line = Line(text="Some say things about it.", sources=(source.id,),
               connective=False, visual=visual)
    lb = LineBeat(label, 0, line, start, end)
    charts = (ChartBeat(label, 0, visual, source, start, end),) if with_list else ()
    section = Section(id=label, heading=heading, side=side, lines=(line,))
    return SectionBeat(label, section, 3, start, end, (lb,), charts)


def _pair(items_a=None, items_b=None, source_b=SOURCE, with_list=True):
    return (_side_section("no", "Why some vote no", "no", 100, 300, with_list, items_a),
            _side_section("yes", "Why some vote yes", "yes", 300, 500, with_list, items_b,
                          source=source_b))


def _inside(test, box, st):
    test.assertGreaterEqual(box.x, st.x - 1e-6)
    test.assertGreaterEqual(box.y, st.y - 1e-6)
    test.assertLessEqual(box.right, st.right + 1e-6)
    test.assertLessEqual(box.bottom, st.bottom + 1e-6)


class SideBoxesTest(unittest.TestCase):
    def test_congruent_and_fit_the_stage(self):
        for fmt in ("9x16", "16x9"):
            L = m.LAYOUTS[fmt]
            a, b = m.side_boxes(L, fmt)
            self.assertAlmostEqual(a.w, b.w)
            self.assertAlmostEqual(a.h, b.h)
            for box in (a, b):
                _inside(self, box, L["stage"])

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
        a, b = _pair(with_list=False)
        plan = m.sides_plan(a, b, L, "9x16")
        items, marks, first = m.side_block(a, L, plan["blocks"][0], 104, plan)
        self.assertTrue(items)  # the label's own strokes
        self.assertEqual([mk.name for mk in marks], ["heading"])
        self.assertIsNone(first)

    def test_a_shared_source_is_left_to_the_slide(self):
        L = m.LAYOUTS["9x16"]
        a, b = _pair()
        plan = m.sides_plan(a, b, L, "9x16")
        items, marks, _ = m.side_block(a, L, plan["blocks"][0], 104, plan)
        self.assertEqual(sorted(mk.name for mk in marks), ["chart", "heading"])
        self.assertGreater(len(items), 2)  # label + 2 check marks + text

    def test_its_own_source_when_the_sides_cite_different_ones(self):
        L = m.LAYOUTS["9x16"]
        a, b = _pair(source_b=OTHER)
        plan = m.sides_plan(a, b, L, "9x16")
        self.assertIsNone(plan["source"])
        _, marks, _ = m.side_block(a, L, plan["blocks"][0], 104, plan)
        self.assertEqual(sorted(mk.name for mk in marks), ["chart", "chart source", "heading"])


class SidesGroupTest(unittest.TestCase):
    def _marks(self, layout, fmt, **kw):
        L = m.LAYOUTS[fmt]
        a, b = _pair(**kw)
        plan = m.sides_plan(a, b, L, fmt, layout)
        _, marks = m.sides_group(a, b, L, fmt, 104, layout)
        return L, plan, marks

    def test_fixed_heading_plus_one_label_per_side(self):
        for layout in LAYOUTS:
            _, _, marks = self._marks(layout, "9x16")
            self.assertEqual(sum(1 for mk in marks if mk.name == "heading"), 3)

    def test_one_source_line_under_both_when_they_share_it(self):
        for layout in LAYOUTS:
            for fmt in ("9x16", "16x9"):
                L, plan, marks = self._marks(layout, fmt)
                srcs = [mk.box for mk in marks if mk.name == "chart source"]
                self.assertEqual(len(srcs), 1, (layout, fmt))
                below = max(mk.box.bottom for mk in marks if mk.name == "chart")
                self.assertGreater(srcs[0].y, below)
                _inside(self, srcs[0], L["stage"])

    def test_each_its_own_source_in_the_same_place_when_they_differ(self):
        for layout in LAYOUTS:
            for fmt in ("9x16", "16x9"):
                _, plan, marks = self._marks(layout, fmt, source_b=OTHER)
                srcs = [mk.box for mk in marks if mk.name == "chart source"]
                self.assertEqual(len(srcs), 2, (layout, fmt))
                a, b = plan["blocks"]
                self.assertAlmostEqual(srcs[0].y - a.y, srcs[1].y - b.y, places=3)
                self.assertAlmostEqual(srcs[0].x - a.x, srcs[1].x - b.x, places=3)

    def test_blocks_are_congruent_and_on_the_stage(self):
        # STANDARD.md rule 7.4: the blocks' rows sit at the same place in
        # each block, the same size, even when one side's item takes two
        # lines and the other's one.
        for layout in LAYOUTS:
            for fmt in ("9x16", "16x9"):
                L, plan, marks = self._marks(layout, fmt,
                                             items_a=["Short point", "Another short one"],
                                             items_b=[LONG, "Stops overspending"])
                box_a, box_b = plan["blocks"]
                self.assertAlmostEqual(box_a.w, box_b.w, places=3)
                self.assertAlmostEqual(box_a.h, box_b.h, places=3)
                charts = [mk.box for mk in marks if mk.name == "chart"]
                self.assertEqual(len(charts), 2)
                a, b = charts
                self.assertAlmostEqual(a.y - box_a.y, b.y - box_b.y, places=3)
                self.assertAlmostEqual(a.x - box_a.x, b.x - box_b.x, places=3)
                self.assertAlmostEqual(a.h, b.h, places=3)
                self.assertAlmostEqual(a.w, b.w, places=3)
                labels = [mk.box for mk in marks if mk.name == "heading"][1:]
                self.assertAlmostEqual(labels[0].y - box_a.y, labels[1].y - box_b.y, places=3)
                for box in plan["cards"] or plan["blocks"]:
                    _inside(self, box, L["stage"])
                if fmt == "9x16":
                    self.assertGreater(box_b.y, box_a.bottom)
                else:
                    self.assertAlmostEqual(box_a.y, box_b.y, places=3)  # top-aligned
                    self.assertGreater(box_b.x, box_a.right)

    def test_rows_pack_at_half_a_line_and_take_at_most_two_lines(self):
        for layout in LAYOUTS:
            for fmt in ("9x16", "16x9"):
                _, plan, marks = self._marks(layout, fmt)
                rows = plan["rows"]
                lh = m.text.line_height(rows["font"])
                self.assertEqual(rows["gap"], round(lh * 0.5))
                self.assertAlmostEqual(rows["rows_h"], sum(rows["heights"]) + rows["gap"], places=3)
                self.assertTrue(all(len(b) <= m.LIST_MAX_LINES for w in rows["wrapped"] for b in w))
                # short items: one line each, however much room is left
                for mk in marks:
                    if mk.name == "chart":
                        self.assertAlmostEqual(mk.box.h, 2 * lh + rows["gap"], places=3)

    def test_compact_blocks_are_further_apart_than_their_rows(self):
        L, plan, _ = self._marks("compact", "9x16")
        a, b = plan["blocks"]
        self.assertGreaterEqual(b.y - a.bottom, 2 * plan["rows"]["gap"] - 1e-6)

    def test_compact_and_cards_centre_the_group_on_the_stage(self):
        for layout in ("compact", "cards"):
            L, plan, _ = self._marks(layout, "9x16")
            st = L["stage"]
            top = (plan["cards"] or plan["blocks"])[0].y
            self.assertAlmostEqual(top - st.y, st.bottom - plan["source"].bottom, places=3)

    def test_cards_are_the_same_size_and_hold_their_blocks(self):
        for fmt in ("9x16", "16x9"):
            _, plan, _ = self._marks("cards", fmt)
            ca, cb = plan["cards"]
            self.assertAlmostEqual(ca.w, cb.w, places=3)
            self.assertAlmostEqual(ca.h, cb.h, places=3)
            for card, block in zip(plan["cards"], plan["blocks"]):
                self.assertGreater(block.x, card.x)
                self.assertGreater(block.y, card.y)
                self.assertLess(block.right, card.right)
                self.assertLess(block.bottom, card.bottom)

    def test_halves_pack_at_the_top_of_each_half_and_the_source_at_the_bottom(self):
        for fmt in ("9x16", "16x9"):
            L, plan, _ = self._marks("halves", fmt)
            st = L["stage"]
            a, b = plan["blocks"]
            self.assertAlmostEqual(a.y, st.y, places=3)
            self.assertAlmostEqual(plan["source"].bottom, st.bottom, places=3)
            # each block keeps its fixed half whatever its words
            _, other, _ = self._marks("halves", fmt, items_a=[LONG, LONG], items_b=[LONG, LONG])
            self.assertAlmostEqual(other["blocks"][1].y, b.y, places=3)
            self.assertAlmostEqual(other["blocks"][1].x, b.x, places=3)


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
