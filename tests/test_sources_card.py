"""film/measure.py's closing sources card: the numbered list fills the
page from under the heading to where the caption would be, its spare
height shared out evenly, as the sides slide's cards do."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ballotreels.contest import load_contest
from ballotreels.storyboard import SOURCES_CARD_SECONDS, cited_sources
from film import measure as m

REPO = Path(__file__).resolve().parent.parent
# DC Initiative 86: 14 cited sources, most of them two or three lines long
MANY = REPO / "data" / "dc-2026-11-03" / "initiative-86"


def lettering(fn, *args):
    """Call fn(*args), recording every line of lettering it writes: (result,
    [(words, font)])."""
    seen = []
    real = m.text_item

    def spy(f0, f1, words, fnt, *a, **kw):
        seen.append((words, fnt))
        return real(f0, f1, words, fnt, *a, **kw)
    with mock.patch.object(m, "text_item", spy):
        return fn(*args), seen


class SourcesCardTest(unittest.TestCase):
    def test_the_list_spans_the_stage_from_heading_to_caption(self):
        for fmt in ("9x16", "16x9"):
            L = m.LAYOUTS[fmt]
            _, marks = m.sources_card(L, 0, 10 ** 6)
            heading, = [mk.box for mk in marks if mk.name == "heading"]
            listed, = [mk.box for mk in marks if mk.name == "sources"]
            room = m.sources_room(L, heading)
            self.assertAlmostEqual(room.bottom, L["scrap"].bottom, places=3)
            self.assertGreater(room.y, heading.bottom)
            n = len(m.BOARD.cited)
            # the spare height: as much above the list as below it, and
            # the same again added to each gap between two sources
            above, below = listed.y - room.y, room.bottom - listed.bottom
            self.assertAlmostEqual(above, below, places=3, msg=fmt)
            self.assertGreaterEqual(above, 0)
            self.assertLessEqual(above, room.h / (n + 1) + 1e-6)
            # nor is the list a band at the top: it covers most of the room
            self.assertGreater(listed.h, room.h * 0.6, fmt)

    def test_the_list_is_as_large_as_the_sides_slide_items(self):
        # Prop 2's few sources fit at the largest size the card allows
        for fmt in ("9x16", "16x9"):
            L = m.LAYOUTS[fmt]
            _, seen = lettering(m.sources_card, L, 0, 10 ** 6)
            sizes = {fnt.size for words, fnt in seen if words != "Sources"}
            self.assertEqual(sizes, {L["sources_font"].size}, fmt)
            self.assertGreaterEqual(L["sources_font"].size, L["heading_font"].size * m.ITEM_MAX - 1)


    def card(self, L, f0=8):
        """The card laid out from f0 + 8 on a film that ends
        SOURCES_CARD_SECONDS after f0, as layout_plan places it."""
        end = f0 + m.to_frame(SOURCES_CARD_SECONDS, m.FPS)
        items, _ = m.sources_card(L, f0 + 8, end)
        return items, end

    def assert_written_in_time(self, items, end, msg):
        # the last source fully written, then still for SOURCES_HOLD
        # before the film's last frame (end - 1)
        last = max(it.f1 for it in items)
        hold = m.to_frame(m.SOURCES_HOLD, m.FPS)
        self.assertLessEqual(last, end - 1 - hold, msg)
        self.assertGreaterEqual(m.SOURCES_HOLD, 1.5)

    def test_every_source_is_written_before_the_film_ends(self):
        for fmt in ("9x16", "16x9"):
            items, end = self.card(m.LAYOUTS[fmt])
            self.assert_written_in_time(items, end, fmt)

    def test_many_long_sources_are_written_before_the_film_ends(self):
        cited = cited_sources(load_contest(MANY))
        self.assertGreaterEqual(len(cited), 14)
        with mock.patch.object(m, "BOARD", SimpleNamespace(cited=cited)):
            for fmt in ("9x16", "16x9"):
                items, end = self.card(m.LAYOUTS[fmt])
                self.assert_written_in_time(items, end, fmt)
                # every source still gets its number and its words
                self.assertGreater(len(items), 2 * len(cited), fmt)

    def test_a_card_that_finishes_in_time_is_unchanged(self):
        # two sources finish well inside the card: their timing is what
        # it would be with all the time in the world
        few = m.BOARD.cited[:2]
        with mock.patch.object(m, "BOARD", SimpleNamespace(cited=few)):
            for fmt in ("9x16", "16x9"):
                L = m.LAYOUTS[fmt]
                items, _ = self.card(L)
                free, _ = m.sources_card(L, 16, 10 ** 6)
                self.assertEqual([(it.f0, it.f1) for it in items],
                                 [(it.f0, it.f1) for it in free], fmt)


if __name__ == "__main__":
    unittest.main()
