"""film/measure.py's closing sources card: the numbered list fills the
page from under the heading to where the caption would be, its spare
height shared out evenly, as the sides slide's cards do."""

import unittest
from unittest import mock

from film import measure as m


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
            _, marks = m.sources_card(L, 0)
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
            _, seen = lettering(m.sources_card, L, 0)
            sizes = {fnt.size for words, fnt in seen if words != "Sources"}
            self.assertEqual(sizes, {L["sources_font"].size}, fmt)
            self.assertGreaterEqual(L["sources_font"].size, L["heading_font"].size * m.ITEM_MAX - 1)


if __name__ == "__main__":
    unittest.main()
