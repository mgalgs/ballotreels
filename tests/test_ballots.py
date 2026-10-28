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
        # a "No." between the word and the number is skipped
        self.assertEqual(designation(
            "Initiative Measure No. 86: Prohibiting Force-Feeding of Birds "
            "Act of 2026", "86"), "Measure")
        self.assertIsNone(designation("2: Untitled", "2"))
        # the number in the title's body, not its lead, does not count
        self.assertIsNone(designation("Taxes: Amendment A", "A"))

    def test_badge_is_the_states_own(self):
        self.assertEqual(badge(BALLOTS["ca"], "Proposition 2: X", "2"), "PROP")
        self.assertEqual(badge(BALLOTS["ut"], "Constitutional Amendment B: X",
                               "B"), "AMENDMENT")

    def test_dc_and_florida_badges(self):
        self.assertEqual(badge(BALLOTS["dc"], "Initiative Measure No. 86: X",
                               "86"), "INITIATIVE")
        self.assertEqual(badge(BALLOTS["fl"], "Amendment 1: X", "1"),
                         "AMENDMENT")

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

    def test_idaho_uses_its_pamphlets_words(self):
        id_ = BALLOTS["id"]
        self.assertEqual((id_.guide, id_.fiscal_label, id_.choices),
                         ("Idaho Voter Pamphlet", "FISCAL IMPACT STATEMENT",
                          ("Yes", "No")))
        self.assertEqual(badge(id_, "Proposition 1: X", "1"), "PROPOSITION")
        self.assertEqual(badge(id_, "House Joint Resolution 4: X", "4"),
                         "RESOLUTION")

    def test_arizona_uses_its_guides_words(self):
        az = BALLOTS["az"]
        self.assertEqual((az.guide, az.fiscal_label, az.choices,
                          az.card_source_kind),
                         ("Arizona's General Election Guide", None,
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(az, "Proposition 317: X", "317"),
                         "PROPOSITION")

    def test_ohio_uses_its_reports_words(self):
        oh = BALLOTS["oh"]
        self.assertEqual((oh.guide, oh.fiscal_label, oh.choices,
                          oh.card_source_kind),
                         ("Proposed Amendment to the Ohio Constitution", None,
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(oh, "State Issue 3: X", "3"), "ISSUE")

    def test_montana_uses_its_pamphlets_words(self):
        mt = BALLOTS["mt"]
        self.assertEqual((mt.guide, mt.fiscal_label, mt.choices,
                          mt.card_source_kind),
                         ("Voter Information Pamphlet", None,
                          ("Yes", "No"), "official-title-summary"))
        # "YES on Constitutional Amendment CI-132", "YES on Initiative I-194"
        self.assertEqual(badge(mt, "Constitutional Amendment CI-132: X",
                               "CI-132"), "AMENDMENT")
        self.assertEqual(badge(mt, "Initiative I-194: X", "I-194"),
                         "INITIATIVE")

    def test_nevada_uses_its_booklets_words(self):
        nv = BALLOTS["nv"]
        self.assertEqual((nv.guide, nv.fiscal_label, nv.choices,
                          nv.card_source_kind),
                         ("Statewide Ballot Questions", "Fiscal Note",
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(nv, "Question 6: X", "6"), "QUESTION")

    def test_new_mexico_uses_its_voter_guides_words(self):
        nm = BALLOTS["nm"]
        self.assertEqual((nm.guide, nm.fiscal_label, nm.choices,
                          nm.card_source_kind),
                         ("General Election Voter Guide", None,
                          ("For", "Against"), "official-title-summary"))
        self.assertEqual(badge(nm, "Constitutional Amendment 1: X", "1"),
                         "AMENDMENT")
        self.assertEqual(badge(nm, "Bond Question 1: X", "1"),
                         "BOND QUESTION")


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
