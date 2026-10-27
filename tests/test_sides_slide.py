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
    def _marks(self, fmt, **kw):
        L = m.LAYOUTS[fmt]
        a, b = _pair(**kw)
        plan = m.sides_plan(a, b, L, fmt)
        _, marks = m.sides_group(a, b, L, fmt, 104)
        return L, plan, marks

    def test_fixed_heading_plus_one_label_per_side(self):
        _, _, marks = self._marks("9x16")
        self.assertEqual(sum(1 for mk in marks if mk.name == "heading"), 3)

    def test_one_source_line_under_both_when_they_share_it(self):
        for fmt in ("9x16", "16x9"):
            L, plan, marks = self._marks(fmt)
            srcs = [mk.box for mk in marks if mk.name == "chart source"]
            self.assertEqual(len(srcs), 1, fmt)
            below = max(mk.box.bottom for mk in marks if mk.name == "chart")
            self.assertGreater(srcs[0].y, below)
            self.assertGreater(srcs[0].y, plan["cards"][1].bottom)

    def test_each_its_own_source_in_the_same_place_when_they_differ(self):
        for fmt in ("9x16", "16x9"):
            _, plan, marks = self._marks(fmt, source_b=OTHER)
            srcs = [mk.box for mk in marks if mk.name == "chart source"]
            self.assertEqual(len(srcs), 2, fmt)
            a, b = plan["blocks"]
            self.assertAlmostEqual(srcs[0].y - a.y, srcs[1].y - b.y, places=3)
            self.assertAlmostEqual(srcs[0].x - a.x, srcs[1].x - b.x, places=3)

    def test_blocks_are_congruent_and_on_the_stage(self):
        # STANDARD.md rule 7.4: the blocks' rows sit at the same place in
        # each block, the same size, even when one side's item takes two
        # lines and the other's one.
        for fmt in ("9x16", "16x9"):
            L, plan, marks = self._marks(fmt,
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
            top, bottom = m.sides_room(L)
            for box in plan["cards"]:
                _inside(self, box, m.Box(0, top, L["W"], bottom - top))
            if fmt == "9x16":
                self.assertGreater(box_b.y, box_a.bottom)
            else:
                self.assertAlmostEqual(box_a.y, box_b.y, places=3)  # top-aligned
                self.assertGreater(box_b.x, box_a.right)

    def test_rows_take_at_most_two_lines_at_a_gap_of_half_a_line_or_more(self):
        for fmt in ("9x16", "16x9"):
            _, plan, marks = self._marks(fmt)
            rows = plan["rows"]
            lh = m.text.line_height(rows["font"])
            self.assertGreaterEqual(rows["gap"], round(lh * 0.5))
            self.assertAlmostEqual(rows["rows_h"], sum(rows["heights"]) + rows["gap"], places=3)
            self.assertTrue(all(len(b) <= m.LIST_MAX_LINES for w in rows["wrapped"] for b in w))
            for mk in marks:
                if mk.name == "chart":
                    self.assertAlmostEqual(mk.box.h, rows["rows_h"], places=3)

    def test_cards_span_the_room_between_heading_and_caption(self):
        for fmt in ("9x16", "16x9"):
            for kw in ({}, dict(source_b=OTHER), dict(with_list=False)):
                L, plan, marks = self._marks(fmt, **kw)
                heading = marks[0].box
                caption = L["scrap"]
                gap = m.EDGE_GAP * L["u"]
                ca, cb = plan["cards"]
                self.assertAlmostEqual(ca.y - heading.bottom, gap, places=3, msg=(fmt, kw))
                last = plan["source"].bottom if plan["source"] else cb.bottom
                self.assertAlmostEqual(caption.y - last, gap, places=3, msg=(fmt, kw))
                if fmt == "9x16":
                    self.assertAlmostEqual(cb.y - ca.bottom, m.CARD_GAP * L["u"], places=3)
                else:
                    self.assertAlmostEqual(ca.y, cb.y, places=3)
                    self.assertAlmostEqual(ca.h, cb.h, places=3)

    def test_spare_height_goes_evenly_to_the_row_gaps_and_padding(self):
        # no band of empty paper in one place: what the text leaves is
        # added alike above and below each block and between its rows
        for fmt in ("9x16", "16x9"):
            L, plan, _ = self._marks(fmt)
            rows = plan["rows"]
            least_gap = round(m.text.line_height(rows["font"]) * 0.5)
            extra_gap = rows["gap"] - least_gap
            for card, block in zip(plan["cards"], plan["blocks"]):
                self.assertAlmostEqual(block.y - card.y - m.CARD_PAD * L["u"], extra_gap, places=3)
                self.assertAlmostEqual(card.bottom - block.bottom - m.CARD_PAD * L["u"], extra_gap,
                                       places=3)
            # and the block's contents end at its own bottom
            block = plan["blocks"][0]
            used = plan["label_h"] + m.LABEL_GAP * L["u"] + rows["rows_h"]
            self.assertAlmostEqual(used, block.h, places=3)

    def test_short_items_grow_past_the_page_lists_type(self):
        for fmt in ("9x16", "16x9"):
            L, plan, _ = self._marks(fmt)
            self.assertGreater(plan["rows"]["font"].size, L["timeline_font"].size * 1.2)
            self.assertGreater(plan["label_font"].size, plan["rows"]["font"].size)

    def test_cards_are_the_same_size_and_hold_their_blocks(self):
        for fmt in ("9x16", "16x9"):
            _, plan, _ = self._marks(fmt)
            ca, cb = plan["cards"]
            self.assertAlmostEqual(ca.w, cb.w, places=3)
            self.assertAlmostEqual(ca.h, cb.h, places=3)
            for card, block in zip(plan["cards"], plan["blocks"]):
                self.assertGreater(block.x, card.x)
                self.assertGreater(block.y, card.y)
                self.assertLess(block.right, card.right)
                self.assertLess(block.bottom, card.bottom)


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

    def test_the_cards_keep_the_same_small_even_margin_at_both_sides(self):
        # the operator's markup: no wide gutter left of the checks or
        # margin right of the text, and both cards alike (rule 7.4)
        for fmt in ("9x16", "16x9"):
            L, plan, marks = self._marks(fmt, items_a=["Short point", LONG],
                                         items_b=[LONG, "Stops overspending"])
            pad = m.CARD_PAD * L["u"]
            for card, block in zip(plan["cards"], plan["blocks"]):
                self.assertAlmostEqual(block.x - card.x, pad, places=3)
                self.assertAlmostEqual(card.right - block.right, pad, places=3)
            rows = plan["rows"]
            self.assertEqual(rows["cx"], 0)  # the checks at the block's left edge
            self.assertAlmostEqual(rows["tx"] + rows["width"], plan["blocks"][0].w, places=3)
            # a long item's first line runs out close to the right edge
            first = m.text.measure(m.list_wrap(LONG, rows["font"], rows["width"])[0], rows["font"])
            self.assertGreater(first, rows["width"] * 0.85)
            charts = [mk.box for mk in marks if mk.name == "chart"]
            for card, chart in zip(plan["cards"], charts):
                self.assertAlmostEqual(chart.x - card.x, pad, places=3)

    def test_yes_and_no_cards_have_identical_geometry(self):
        for fmt in ("9x16", "16x9"):
            _, plan, marks = self._marks(fmt, items_a=["No argument against was submitted"],
                                         items_b=[LONG, "Stops overspending"])
            ca, cb = plan["cards"]
            ba, bb = plan["blocks"]
            self.assertEqual((ca.w, ca.h), (cb.w, cb.h))
            self.assertEqual((ba.w, ba.h), (bb.w, bb.h))
            self.assertEqual((ba.x - ca.x, ba.y - ca.y), (bb.x - cb.x, bb.y - cb.y))
            a, b = [mk.box for mk in marks if mk.name == "chart"]
            self.assertAlmostEqual(a.x - ba.x, b.x - bb.x, places=6)
            self.assertAlmostEqual(a.y - ba.y, b.y - bb.y, places=6)


class ListWrapTest(unittest.TestCase):
    def test_fills_the_first_line_but_never_leaves_a_lone_word(self):
        fnt = m.font(50, family=m.PRINT)
        lines = m.list_wrap(LONG, fnt, 900)
        self.assertGreater(m.text.measure(lines[0], fnt), 800)
        for w in range(300, 1200, 7):
            lines = m.list_wrap(LONG, fnt, w)
            if len(lines) > 1:
                self.assertIn(" ", lines[-1].strip(), w)
