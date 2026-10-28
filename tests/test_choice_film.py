"""film/measure.py for a choice question: the card lists the choices, and
the `choices` section draws them on a grid (STANDARD.md section 8)."""

import tempfile
import unittest
from pathlib import Path

from ballotreels import grid

from .choice_fixture import (label, write_choice_contest,
                             write_stand_in_sidecars)
from .choice_fixture import load_film as _load_film

_FILMS = {}


def load_film(n):
    """The film for a made-up question with `n` options, loaded once."""
    if n not in _FILMS:
        tmp = tempfile.TemporaryDirectory()
        path = write_choice_contest(Path(tmp.name) / f"c{n}", n)
        write_stand_in_sidecars(path)
        _FILMS[n] = (tmp, _load_film(path))
    return _FILMS[n][1]


def tearDownModule():
    for tmp, _ in _FILMS.values():
        tmp.cleanup()
    _FILMS.clear()


class GridPlanTest(unittest.TestCase):
    def test_cells_alike_in_reading_order(self):
        for n in (2, 3, 4, 5, 6, 7, 8, 13):
            m = load_film(n)
            for fmt in ("9x16", "16x9"):
                with self.subTest(n=n, fmt=fmt):
                    plan = m.choices_plan(fmt)
                    sizes = {(round(b.w, 6), round(b.h, 6)) for page in plan["cells"] for b in page}
                    self.assertEqual(len(sizes), 1)  # one cell size on every page
                    self.assertEqual([len(p) for p in plan["cells"]], list(grid.page_sizes(n)))
                    for page in plan["cells"]:
                        # reading order: left to right, then top to bottom
                        keys = [(round(b.y), round(b.x)) for b in page]
                        self.assertEqual(keys, sorted(keys))
                        st = m.LAYOUTS[fmt]["stage"]
                        for b in page:
                            self.assertGreaterEqual(b.x, st.x - 1e-6)
                            self.assertLessEqual(b.right, st.right + 1e-6)
                            self.assertGreaterEqual(b.y, st.y - 1e-6)
                            self.assertLessEqual(b.bottom, st.bottom + 1e-6)

    def test_grid_shape_on_each_frame(self):
        m = load_film(6)
        self.assertEqual(m.grid_shape(6, "9x16"), (2, 3))
        self.assertEqual(m.grid_shape(6, "16x9"), (3, 2))  # turned on its side
        self.assertEqual(m.grid_shape(3, "9x16"), (1, 3))
        self.assertEqual(m.grid_shape(3, "16x9"), (3, 1))

    def test_five_leave_the_last_cell_empty(self):
        m = load_film(5)
        (page,) = m.choices_plan("9x16")["cells"]
        self.assertEqual(len(page), 5)
        xs = sorted({round(b.x) for b in page})
        ys = sorted({round(b.y) for b in page})
        self.assertEqual((len(xs), len(ys)), (2, 3))
        # the fifth sits alone at the left of the last row, its own size
        self.assertEqual((round(page[4].x), round(page[4].y)), (xs[0], ys[2]))
        self.assertAlmostEqual(page[4].w, page[0].w)


class GridDrawTest(unittest.TestCase):
    def _cells(self, m, fmt="9x16"):
        charts = [c for c in m.BOARD.charts if c.visual.kind == "choices"]
        sec = next(s for s in m.BOARD.sections if s.section.id == "choices")
        out = []
        for chart in charts:
            run = next(r for r in m.runs_of(sec) if r[1] is chart)
            items, marks = m.chart_run(chart, run[2], m.LAYOUTS[fmt], chart.start + 4)
            out.append((chart, items, marks))
        return out

    def test_one_page_per_visual(self):
        m = load_film(7)
        got = self._cells(m)
        self.assertEqual([m.choice_page(c) for c, _, _ in got], [0, 1])

    def test_every_cell_draws_in_the_same_time(self):
        m = load_film(6)
        (chart, items, marks), = self._cells(m)
        plan = m.choices_plan("9x16")
        spans = []
        for box in plan["cells"][0]:
            mine = [it for it in items if it.f1 - it.f0 > 0 and it._head is not None
                    and box.x <= it.head(it.f1)[0] <= box.right
                    and box.y <= it.head(it.f1)[1] <= box.bottom]
            # the outline drawn on with the others, then the drawing and label
            body = [it for it in mine if it.f0 > chart.start + 4 + 12]
            spans.append(round(max(it.f1 for it in body) - min(it.f0 for it in body), 6))
        self.assertEqual(len(set(spans)), 1, spans)

    def test_labels_alike(self):
        m = load_film(6)
        plan = m.choices_plan("9x16")
        self.assertLessEqual(max(len(m.text.wrap(m.CHOICES[k].printed, plan["font"], plan["art"][2],
                                                 balance=True)) for k in range(6)),
                             m.CELL_LABEL_LINES)


class CardTest(unittest.TestCase):
    def test_lists_every_choice_in_one_face(self):
        m = load_film(6)
        for fmt in ("9x16", "16x9"):
            _, parts = m.page_plan(fmt)
            flows = [f for f in parts["flows"] if f.field.startswith("choice ")]
            self.assertEqual([f.field for f in flows], [f"choice {k}" for k in range(6)])
            words = [" ".join(r[0] for r in f.runs) for f in flows]
            self.assertEqual(words, [f"({chr(97 + k)}) {label(k)}" for k in range(6)])
            self.assertEqual(len({id(r[1]) for f in flows for r in f.runs}), 1)
            self.assertIn(m.CHOICES_HEADING, [lab[0] for lab in parts["labels"]])
            self.assertNotIn("WHAT YOUR VOTE MEANS", [lab[0] for lab in parts["labels"]])
            # in reading order, top to bottom
            ys = [f.y for f in flows]
            self.assertEqual(ys, sorted(ys))

    def test_no_choice_highlighted(self):
        m = load_film(6)
        _, parts = m.page_plan("9x16")
        self.assertEqual(m.focus_boxes(parts, "Model A tree"), [])
        self.assertTrue(m.focus_boxes(parts, "Which tree"))

    def test_the_ballot_lists_the_choices(self):
        m = load_film(3)
        sec = m.BOARD.sections[0]
        items, marks = m.ballot_run(sec.lines, m.LAYOUTS["9x16"], 4)
        self.assertEqual([mk.name for mk in marks], ["ballot"])
        self.assertTrue(items)


if __name__ == "__main__":
    unittest.main()
