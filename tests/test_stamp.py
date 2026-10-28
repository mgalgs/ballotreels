"""film/measure.py: an illustration's `stamp` is written across its top in
the film's hand and graphite, large enough to read on a phone, between
the heading and the caption; without one the illustration is as it was."""

import unittest
from unittest import mock

from ballotreels.contest import Visual
from ballotreels.storyboard import ChartBeat

from film import measure as m


def run(v, fmt):
    """illustration_visual of `v` in `fmt`: (items, marks, [(words, font, ink)])."""
    seen = []
    real = m.text_item

    def spy(f0, f1, words, fnt, x, y, ink=m.GRAPHITE, *a, **kw):
        seen.append((words, fnt, ink))
        return real(f0, f1, words, fnt, x, y, ink, *a, **kw)
    chart = ChartBeat("fiscal", 0, v, None, 100, 400)
    with mock.patch.object(m, "text_item", spy):
        items, marks = m.illustration_visual(chart, [], m.LAYOUTS[fmt], 100, 400)
    return items, marks, seen


PLAIN = Visual(kind="illustration", name="analyst-review")
STAMPED = Visual(kind="illustration", name="analyst-review", stamp="None reported")


class StampTest(unittest.TestCase):
    def test_the_stamp_is_written_in_the_hand_and_graphite(self):
        for fmt in ("9x16", "16x9"):
            _, _, seen = run(STAMPED, fmt)
            [(words, fnt, ink)] = seen
            self.assertEqual(words, "None reported")
            self.assertEqual(fnt.family, m.HAND)
            self.assertEqual(ink, m.GRAPHITE)
            self.assertGreaterEqual(fnt.size, m.LAYOUTS[fmt]["chart_title_font"].size, fmt)

    def test_the_stamp_sits_on_the_stage_above_the_drawing(self):
        for fmt in ("9x16", "16x9"):
            L = m.LAYOUTS[fmt]
            items, [mark], _ = run(STAMPED, fmt)
            stage = L["stage"]
            self.assertGreaterEqual(mark.box.y, stage.y, fmt)
            self.assertLessEqual(mark.box.bottom, stage.bottom, fmt)
            self.assertGreater(mark.box.y, L["heading"].bottom, fmt)
            self.assertLess(mark.box.bottom, L["scrap"].y, fmt)
            stamp = items[-1]
            self.assertGreaterEqual(stamp.f0, items[0].f1)  # once the drawing is down
            self.assertLess(stamp.f1, 400)
            # the stamp is the mark's top, the drawing below it
            _, sy, _, sh = stamp.box
            self.assertAlmostEqual(sy, mark.box.y, places=6)
            self.assertLess(sy + sh, mark.box.bottom - 0.4 * mark.box.h)

    def test_without_a_stamp_nothing_is_written(self):
        for fmt in ("9x16", "16x9"):
            items, [mark], seen = run(PLAIN, fmt)
            self.assertEqual(seen, [])
            self.assertEqual(len(items), 1)
            stage = m.LAYOUTS[fmt]["stage"]
            self.assertAlmostEqual(mark.box.cy, stage.cy, places=6)


if __name__ == "__main__":
    unittest.main()
