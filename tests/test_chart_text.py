"""film/measure.py's charts letter their titles, labels and values large
enough to read on a phone: the chart grows its text, not its marks."""

import unittest

from ballotreels.contest import Source, Visual
from ballotreels.storyboard import ChartBeat

from film import measure as m
from tests.test_sources_card import lettering

SOURCE = Source(id="lao", kind="official-analysis", publisher="Pub", url="https://example.com",
                file="sources/a.html", retrieved="2026-01-01")

CHARTS = [
    Visual(kind="bars", source="lao", title="Rainy Day Fund target, share of main-budget taxes",
           unit="%", labels=["Today", "Proposition 2"], values=[10, 20]),
    Visual(kind="share", source="lao", title="Where the money goes", unit="%",
           labels=["Schools", "Health care", "Everything else"], values=[40, 25, 35]),
    Visual(kind="series", source="lao", title="Rainy Day Fund balance each June 30, billions of dollars",
           unit="", labels=[str(y) for y in range(2007, 2026)],
           values=[0.5, 0, 0, 0, 0, 0, 0, 0, 1.6, 3.6, 6.7, 10.8, 13.9, 17.1, 14.3, 19.9, 21.7, 22.9, 18.6]),
    Visual(kind="figure", source="lao", title="Revenue swings; spending grows steadily",
           figure="steady-spending-volatile-revenue"),
]

# the least size, in px at 1080 wide (9:16), of each kind of lettering
LEAST_9X16 = dict(title=52, label=44, axis=40)


def roles(v, seen):
    """Each line of lettering in `seen` with its role: the chart's title,
    an axis value (the print hand), or a category, value or line label."""
    title = " ".join(v.title.split())
    for words, fnt in seen:
        if fnt.family == m.PRINT:
            yield "axis", words, fnt
        elif " " in words and words in title:
            yield "title", words, fnt
        else:
            yield "label", words, fnt


class ChartTextTest(unittest.TestCase):
    def _lettering(self, v, fmt):
        L = m.LAYOUTS[fmt]
        chart = ChartBeat("change", 0, v, SOURCE, 100, 400)
        fn = m.FIGURES[v.figure] if v.kind == "figure" else m.CHARTS[v.kind]
        (_, marks), seen = lettering(fn, chart, L, 100, 400)
        return L, marks, list(roles(v, seen))

    def test_9x16_lettering_reads_on_a_phone(self):
        for v in CHARTS:
            _, _, seen = self._lettering(v, "9x16")
            got = {role for role, _, _ in seen}
            self.assertIn("title", got, v.kind)
            self.assertIn("label", got, v.kind)
            for role, words, fnt in seen:
                self.assertGreaterEqual(fnt.size, LEAST_9X16[role], (v.kind, role, words))

    def test_16x9_grows_in_proportion(self):
        for key in ("chart_title_font", "chart_label_font", "value_font", "axis_font"):
            a, b = m.LAYOUTS["9x16"][key], m.LAYOUTS["16x9"][key]
            self.assertAlmostEqual(b.size / a.size, 0.9, delta=0.02, msg=key)

    def test_the_source_note_is_unchanged(self):
        self.assertEqual(m.LAYOUTS["9x16"]["note_font"].size, 34)
        self.assertEqual(m.LAYOUTS["16x9"]["note_font"].size, 31)

    def test_lettering_stays_on_the_stage(self):
        for fmt in ("9x16", "16x9"):
            for v in CHARTS:
                L, marks, _ = self._lettering(v, fmt)
                st = L["stage"]
                for mk in marks:
                    self.assertGreaterEqual(mk.box.y, st.y - 1e-6, (fmt, v.kind, mk.name))
                    self.assertLessEqual(mk.box.bottom, st.bottom + 1e-6, (fmt, v.kind, mk.name))


if __name__ == "__main__":
    unittest.main()
