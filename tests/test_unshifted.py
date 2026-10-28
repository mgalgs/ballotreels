"""Reading back the Alameda County guide's glyph-id text
(checks._unshifted_text), for the card, basis and glance quotes."""

import unittest
from pathlib import Path

from ballotreels.checks import (_archived_text, _in_unshifted,
                                _loose, _loose_archived, _unshift_line,
                                _unshifted_text)

ROOT = Path(__file__).resolve().parent.parent
PLEASANTON = ROOT / "data/ca-2026-11-03/pleasanton-measure-hh/sources/vig-pp956-958.pdf"
PROP_2 = ROOT / "data/ca-2026-11-03/prop-2/sources"


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
