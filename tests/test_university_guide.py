"""The `university-guide` source kind (STANDARD.md rule 1.2): where a
state publishes no official voter guide, a public university's guide may
explain and give the sides, named every time, and nothing else."""

import unittest

from ballotreels import load_contest
from ballotreels.checks import check_side_basis, check_university_guide

from .helpers import ContestCopyTestCase

ARGUMENTS = ('id = "arguments"\nkind = "official-argument"\n')


class UniversityGuideTest(ContestCopyTestCase):
    """A copy of Prop 2 whose arguments stand in for a university guide's
    "what supporters say" and "what opponents say", its publisher's
    short name "Supporters say" (which only the yes side's first line
    says)."""

    def setUp(self):
        super().setUp()
        self.edit("sources.toml", ARGUMENTS,
                  'id = "arguments"\nkind = "university-guide"\n'
                  'short_name = "Supporters say"\n')

    def failures(self):
        return check_university_guide(load_contest(self.dir))

    def where(self):
        return {(f.section, f.line) for f in self.failures()}

    def test_a_line_naming_the_publisher_passes(self):
        self.assertNotIn(("yes", 0), self.where())

    def test_a_line_not_naming_the_publisher_fails(self):
        got = [f for f in self.failures() if (f.section, f.line) == ("yes", 1)]
        self.assertEqual(len(got), 1, [str(f) for f in got])
        self.assertIn("'Supporters say'", got[0].message)
        self.assertEqual(len(self.failures()), 7)  # every side line but one

    def test_named_on_every_line_passes(self):
        self.edit("sources.toml", 'short_name = "Supporters say"',
                  'short_name = "s"')
        self.assertEqual(self.failures(), [])

    def test_short_name_is_required(self):
        self.edit("sources.toml", 'short_name = "Supporters say"\n', "")
        got = [f for f in self.failures() if f.section is None]
        self.assertEqual(len(got), 1)
        self.assertIn("has no 'short_name'", got[0].message)

    def test_not_in_the_opening_fiscal_or_vote(self):
        self.edit("sources.toml", 'short_name = "Supporters say"',
                  'short_name = "s"')
        self.edit("script.toml",
                  'text = "A no vote means the current rules would not '
                  'change."\nsources = ["quick-reference"]',
                  'text = "A no vote means the current rules would not '
                  'change."\nsources = ["quick-reference", "arguments"]')
        [f] = self.failures()
        self.assertEqual((f.section, f.line), ("vote", 1))
        self.assertIn("'vote' section", f.message)

    def test_not_beside_an_official_guide(self):
        self.edit("sources.toml", 'short_name = "Supporters say"',
                  'short_name = "s"')
        self.edit("sources.toml", 'id = "text"\nkind = "official-text"',
                  'id = "text"\nkind = "official-argument"')
        got = self.failures()
        self.assertEqual(len(got), 8)
        self.assertTrue(all("official voter guide" in f.message for f in got))

    def test_a_basis_may_quote_it(self):
        got = check_side_basis(load_contest(self.dir), required=True)
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main()
