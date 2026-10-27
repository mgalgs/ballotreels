"""film/measure.py's running title (header_fit): the measure's title fills
its band, between the notebook's binding and the section heading, in at
most two lines, and shrinks to fit a long one rather than spill."""

import unittest

from film import measure as m

# the longest California title, as the ballot words it and as the data has it
PROP_3 = ("Proposition 3: Provides permanent funding for schools and health care by "
          "extending existing tax on high incomes. Initiative constitutional amendment.")
PROP_2 = ("Proposition 2: Increases State's Rainy Day Fund. "
          "Legislative Constitutional Amendment.")
BINDING_BOTTOM = 111  # sketch.backdrop: the punched holes' lowest point


class HeaderFitTest(unittest.TestCase):
    def fit(self, title, fmt):
        L = m.LAYOUTS[fmt]
        return L, m.header_fit(title, L["header"], L["header_font"].size)

    def test_the_band_lies_between_the_binding_and_the_heading(self):
        for fmt in ("9x16", "16x9"):
            L = m.LAYOUTS[fmt]
            self.assertGreater(L["header"].y, BINDING_BOTTOM)
            self.assertLessEqual(L["header"].bottom, L["heading"].y)

    def test_the_longest_title_fits_its_band(self):
        for title in (PROP_3, PROP_3.upper()):
            for fmt in ("9x16", "16x9"):
                L, (fnt, lines, y) = self.fit(title, fmt)
                band = L["header"]
                self.assertLessEqual(len(lines), m.HEADER_LINES, (fmt, title))
                self.assertEqual(" ".join(lines), title)  # nothing dropped
                self.assertGreaterEqual(y, band.y)
                self.assertLessEqual(y + m.text.line_height(fnt) * len(lines), band.bottom + 1e-6)
                for ln in lines:
                    self.assertLessEqual(m.text.measure(ln, fnt), band.w)

    def test_a_short_title_grows_to_fill_but_stays_under_the_heading(self):
        for fmt in ("9x16", "16x9"):
            L, (fnt, lines, y) = self.fit(PROP_2, fmt)
            band = L["header"]
            self.assertLess(fnt.size, L["heading_font"].size * 0.7)
            used = m.text.line_height(fnt) * len(lines)
            self.assertGreater(fnt.size, {"9x16": 40, "16x9": 30}[fmt])
            self.assertAlmostEqual(y - band.y, band.bottom - (y + used), places=3)  # centred
