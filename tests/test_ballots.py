"""Each state's ballot wording (ballotreels.ballots), and the checks that
hold a script to its own state's words."""

import shutil
import unittest

from ballotreels import check_contest, load_contest
from ballotreels.ballots import BALLOTS, badge, ballot_for, designation

from .helpers import ContestCopyTestCase
from .test_card import CARD, VERSION


class BallotTest(unittest.TestCase):
    def test_designation_is_the_word_before_the_number(self):
        self.assertEqual(designation("Proposition 2: Increases ...", "2"),
                         "Proposition")
        self.assertEqual(designation(
            "Constitutional Amendment A: Publication Amendments", "A"),
            "Amendment")
        self.assertEqual(designation("Issue 1", "1"), "Issue")
        self.assertIsNone(designation("2: Untitled", "2"))
        # the number in the title's body, not its lead, does not count
        self.assertIsNone(designation("Taxes: Amendment A", "A"))

    def test_badge_is_the_states_own(self):
        self.assertEqual(badge(BALLOTS["ca"], "Proposition 2: X", "2"), "PROP")
        self.assertEqual(badge(BALLOTS["ut"], "Constitutional Amendment B: X",
                               "B"), "AMENDMENT")

    def test_ballot_for_reads_the_divisions_state(self):
        self.assertIs(ballot_for("ocd-division/country:us/state:ut"),
                      BALLOTS["ut"])
        self.assertIs(ballot_for("ocd-division/country:us/state:ca/cd:12"),
                      BALLOTS["ca"])
        self.assertIsNone(ballot_for("ocd-division/country:us/state:zz"))

    def test_california_keeps_its_wording(self):
        ca = BALLOTS["ca"]
        self.assertEqual((ca.fiscal_label, ca.choices, ca.card_source_kind),
                         ("Fiscal Impact:", ("Yes", "No"),
                          "official-title-summary"))

    def test_utah_uses_its_pamphlets_words(self):
        ut = BALLOTS["ut"]
        self.assertEqual((ut.guide, ut.fiscal_label, ut.choices),
                         ("Voter Information Pamphlet", "Fiscal Effects",
                          ("For", "Against")))

    def test_washington_uses_its_pamphlets_words(self):
        wa = BALLOTS["wa"]
        self.assertEqual((wa.guide, wa.fiscal_label, wa.choices,
                          wa.card_source_kind),
                         ("Voters' Pamphlet", "Fiscal Impact Statement",
                          ("Yes", "No"), "official-title-summary"))
        # "Initiative Measure IL26-638", as the pamphlet heads its page
        self.assertEqual(badge(wa, "Initiative Measure IL26-638: X",
                               "IL26-638"), "MEASURE")


class SideHeadingTest(ContestCopyTestCase):
    def failures(self):
        return [str(f) for f in check_contest(load_contest(self.dir))]

    def set_headings(self, yes, no):
        self.edit("script.toml", 'heading = "Supporters say"',
                  f'heading = "{yes}"')
        self.edit("script.toml", 'heading = "Opponents say"',
                  f'heading = "{no}"')

    def test_headings_use_the_ballots_words(self):
        self.set_headings("Why some vote yes", "Why some vote no")
        self.assertEqual(self.failures(), [])

    def test_the_other_sides_word_fails(self):
        self.set_headings("Why some vote yes", "Why some vote yes")
        self.assertEqual(self.failures(), [
            "[side-heading] no: heading 'Why some vote yes' says 'yes'; the "
            "ballot's word for this side is 'No'"])

    def test_another_states_words_fail(self):
        self.set_headings("Why some vote for", "Why some vote against")
        self.assertEqual(self.failures(), [
            "[side-heading] yes: heading 'Why some vote for' says 'for'; the "
            "ballot's word for this side is 'Yes'",
            "[side-heading] no: heading 'Why some vote against' says "
            "'against'; the ballot's word for this side is 'No'"])

    def test_utah_uses_for_and_against(self):
        self.edit("sources.toml", "state:ca", "state:ut")
        self.set_headings("Why some vote yes", "Why some vote against")
        self.assertEqual(self.failures(), [
            "[side-heading] yes: heading 'Why some vote yes' says 'yes'; the "
            "ballot's word for this side is 'For'"])


@unittest.skipIf(shutil.which("pdftotext") is None, "needs pdftotext")
class PdfCardTest(ContestCopyTestCase):
    """A card may quote a PDF (Utah's pamphlet is one): the verbatim check
    reads its text with pdftotext. Prop 2's guide pages print its title,
    but none of the Quick Reference page's other fields."""

    def test_quotes_checked_against_the_pdfs_text(self):
        self.edit("script.toml", VERSION, VERSION + CARD)
        self.edit("script.toml", 'source = "quick-reference"\nnumber',
                  'source = "guide-section"\nnumber')
        got = [str(f) for f in check_contest(load_contest(self.dir))
               if f.check == "card"]
        self.assertEqual(got, [
            f"[card] {key!r} does not appear verbatim in source "
            f"'guide-section' (sources/guide-section.pdf)"
            for key in ("origin", "summary", "yes", "no")])


if __name__ == "__main__":
    unittest.main()
