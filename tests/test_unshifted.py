"""Reading back the Alameda County guide's glyph-id text
(checks._unshifted_text), for the card, basis and glance quotes."""

import unittest
from pathlib import Path

from ballotreels.checks import (_archived_text, _in_unshifted,
                                _loose, _loose_archived, _unshift_line,
                                _unshifted_text)

ROOT = Path(__file__).resolve().parent.parent
PLEASANTON = ROOT / "data/ca-2026-11-03/pleasanton-measure-hh/sources/vig-pp956-958.pdf"
OAKLAND_EE = ROOT / "data/ca-2026-11-03/oakland-measure-ee/sources/vig-pp933-946.pdf"
PROP_2 =ROOT / "data/ca-2026-11-03/prop-2/sources"


class UnshiftTest(unittest.TestCase):
    def test_line(self):
        # "maintain city services, such as:" with a shifted space (\x03)
        self.assertEqual(
            _unshift_line("PDLQWDLQ\x03FLW\\\x03VHUYLFHV\x0f\x03VXFK\x03DV\x1d",
                          True),
            "maintain city services, such as:")

    def test_printed_word_beside_shifted_space(self):
        # a printed "II" beside a shifted space is read both ways
        line = "YES on II\x03UHQHZV\x03"
        self.assertEqual(_unshift_line(line, True), "YES on ff renews ")
        self.assertEqual(_unshift_line(line, False), "YES on II renews ")

    def test_printed_punctuation_ending_a_word_stays(self):
        self.assertEqual(_unshift_line("UHVLGHQWV.\x03", True), "residents. ")

    def test_capital_x(self):
        # X (0x58) comes back as ";", which also ends a printed clause
        self.assertEqual(_unshift_line("$UWLFOH\x03,;\x03RI\x03", True),
                         "Article IX of ")
        self.assertEqual(_unshift_line("\x03;\x03WD[\x03", True),
                         " X tax ")
        self.assertEqual(_unshift_line("\x037$;\x03", False), " TAX ")
        self.assertEqual(_unshift_line("\x03;,,,\x03", False), " XIII ")
        # a printed semicolon after a shifted word stays one
        self.assertEqual(_unshift_line("VHUYLFHV;\x03", True), "services; ")

    def test_a_word_all_punctuation_is_shifted(self):
        self.assertEqual(_unshift_line("\x030HDVXUH\x03,,\x03", False),
                         " Measure II ")

    def test_apostrophe(self):
        # the font's apostrophe comes back as a printed space
        self.assertEqual(_unshift_line("WKH\x03&LW\\ V\x03&KDUWHU", True),
                         "the City’s Charter")
        self.assertEqual(_unshift_line("\x03&LW\\ V\x03", False),
                         " City’s ")
        self.assertEqual(_unshift_line("\x03GRQ W\x03", False), " don’t ")
        self.assertEqual(_unshift_line("\x030D\\RU V\x11\x03", False),
                         " Mayor’s. ")
        # a drop capital's space is not one
        self.assertEqual(_unshift_line("\x037 KH\x03", True), " T he ")

    def test_quotes_with_x_and_apostrophe_found(self):
        self.assertTrue(_in_unshifted(
            "the provisions of Article IX of this Charter", OAKLAND_EE))
        self.assertFalse(_in_unshifted(
            "the provisions of Article XI of this Charter", OAKLAND_EE))
        self.assertTrue(_in_unshifted("following the Mayor's election",
                                      OAKLAND_EE))
        self.assertTrue(_in_unshifted("following the Mayor’s election",
                                      OAKLAND_EE))

    def test_ballot_question_found(self):
        question = ("Shall a measure be adopted to increase the City’s "
                    "Uniform Transient Occupancy Tax paid by hotel guests "
                    "from 8% to 10% on July 1, 2027, and to 12% on July 1, "
                    "2028, generating an estimated $1.4 to $2.8 million per "
                    "year in additional revenue, that can be used to "
                    "maintain city services, such as: police and fire "
                    "protection; park and street maintenance; recreation "
                    "programs; and other general government uses, until "
                    "ended by voters?")
        self.assertNotIn(question, _archived_text(PLEASANTON))
        self.assertTrue(_in_unshifted(question, PLEASANTON))
        self.assertFalse(_in_unshifted(question.replace("8%", "9%"),
                                       PLEASANTON))

    def test_apostrophe_the_font_drops(self):
        quote = ("(3) affirm Councilmembers' right to acquire information "
                 "from other City officials")
        self.assertTrue(_in_unshifted(quote, OAKLAND_EE))
        self.assertFalse(_in_unshifted(quote.replace("other", "all"),
                                       OAKLAND_EE))

    def test_basis_found(self):
        basis = _loose("allows the City to continue providing programs "
                       "and services that benefit all residents")
        self.assertNotIn(basis, _loose(_archived_text(PLEASANTON)))
        self.assertIn(basis, _loose_archived(PLEASANTON))

    def test_other_pdfs_unchanged(self):
        for pdf in sorted(PROP_2.glob("*.pdf")):
            self.assertIsNone(_unshifted_text(pdf), pdf)


if __name__ == "__main__":
    unittest.main()
