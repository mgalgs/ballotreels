"""Each state's ballot wording (ballotreels.ballots), and the checks that
hold a script to its own state's words."""

import shutil
import unittest

from ballotreels import check_contest, load_contest
from ballotreels.ballots import BALLOTS, badge, ballot_for, designation
from ballotreels.checks import _card_quote_in

from ballotreels.ballots import (BALLOTS, badge, ballot_for, designation,
                                 guide_of)

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

    def test_hawaii_badge_and_wording(self):
        hi = BALLOTS["hi"]
        self.assertEqual(badge(hi, "Question 1: X", "1"), "QUESTION")
        self.assertEqual(hi.guide, "2026 Voter Guide")
        self.assertIsNone(hi.fiscal_label)
        self.assertEqual(hi.choices, ("Yes", "No"))

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

    def test_massachusetts_uses_its_booklets_words(self):
        ma = BALLOTS["ma"]
        self.assertEqual((ma.guide, ma.fiscal_label, ma.choices,
                          ma.card_source_kind),
                         ("Information for Voters",
                          "STATEMENT OF FISCAL CONSEQUENCES",
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(ma, "Question 1: X", "1"), "QUESTION")

    def test_north_dakota_uses_its_guides_words(self):
        nd = BALLOTS["nd"]
        self.assertEqual((nd.guide, nd.fiscal_label, nd.choices,
                          nd.card_source_kind),
                         ("North Dakota Statewide Ballot Measure Information",
                          "FISCAL IMPACT", ("Yes", "No"),
                          "official-title-summary"))
        self.assertEqual(badge(nd, "Constitutional Measure No. 1: X", "1"),
                         "MEASURE")
        self.assertEqual(badge(nd, "Initiated Constitutional Measure No. 2: X",
                               "2"), "MEASURE")

    def test_wyoming_uses_its_propositions_words(self):
        wy = BALLOTS["wy"]
        self.assertEqual((wy.guide, wy.fiscal_label, wy.choices,
                          wy.card_source_kind),
                         ("2026 General Election Statewide Ballot Propositions",
                          "Estimated Fiscal Impact:", ("For", "Against"),
                          "official-title-summary"))
        # "PROPOSED INITIATIVE PROPOSITION NUMBER ONE"
        self.assertEqual(badge(wy, "Proposed Initiative Proposition Number "
                                   "One: X", "One"), "PROPOSITION")

    def test_georgia_uses_its_booklets_words(self):
        ga = BALLOTS["ga"]
        self.assertEqual((ga.guide, ga.fiscal_label, ga.choices,
                          ga.card_source_kind),
                         ("Proposed Constitutional Amendments", None,
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(ga, "Amendment 1: X", "1"), "AMENDMENT")

    def test_colorado_uses_its_booklets_words(self):
        co = BALLOTS["co"]
        self.assertEqual((co.guide, co.fiscal_label, co.choices,
                          co.card_source_kind),
                         ("State Ballot Information Booklet",
                          "Fiscal Impact Statement",
                          ("Yes/For", "No/Against"), "official-title-summary"))
        self.assertEqual(badge(co, "Amendment 81: X", "81"), "AMENDMENT")
        self.assertEqual(badge(co, "Proposition NN: X", "NN"), "PROPOSITION")

    def test_rhode_island_uses_its_handbooks_words(self):
        ri = BALLOTS["ri"]
        self.assertEqual((ri.guide, ri.fiscal_label, ri.choices,
                          ri.card_source_kind),
                         ("Voter Information Handbook", "Total cost:",
                          ("Approve", "Reject"), "official-title-summary"))
        self.assertEqual(badge(ri, "Question 1: X", "1"), "QUESTION")

    def test_arkansas_uses_its_notices_words(self):
        ar = BALLOTS["ar"]
        self.assertEqual((ar.guide, ar.fiscal_label, ar.choices,
                          ar.card_source_kind),
                         ("Notice to the Public", None,
                          ("For", "Against"), "official-title-summary"))
        self.assertEqual(badge(ar, "Issue 1: X", "1"), "ISSUE")

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

    def test_virginia_uses_its_explanations_words(self):
        va = BALLOTS["va"]
        self.assertEqual((va.guide, va.fiscal_label, va.choices,
                          va.card_source_kind),
                         ("Explanation for Voters",
                          "State Fiscal Impact Statement", ("Yes", "No"),
                          "official-title-summary"))
        self.assertEqual(badge(va, "Question 1: X", "1"), "QUESTION")

    def test_maryland_uses_its_boards_words(self):
        md = BALLOTS["md"]
        self.assertEqual((md.guide, md.fiscal_label, md.choices,
                          md.card_source_kind),
                         ("Ballot Questions for the November 3, 2026 Election",
                          "Fiscal Summary", ("For", "Against"),
                          "official-title-summary"))
        self.assertEqual(badge(md, "Question 1: X", "1"), "QUESTION")

    def test_louisiana_uses_its_statements_words(self):
        la = BALLOTS["la"]
        self.assertEqual((la.guide, la.fiscal_label, la.choices,
                          la.card_source_kind),
                         ("Statements of Proposed Constitutional Amendments",
                          None, ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(la, "Amendment 1: X", "1"), "AMENDMENT")
        self.assertEqual(badge(la, "Amendment 10: X", "10"), "AMENDMENT")
        self.assertTrue(la.card_column_breaks)
        self.assertFalse(any(b.card_column_breaks
                             for s, b in BALLOTS.items() if s != "la"))


class CardColumnBreakTest(unittest.TestCase):
    """A card quote from a source set in columns may lose a line-end
    hyphen and run across one column break, only where the state's
    entry says its source is set so: the first piece ending one of
    pdftotext's blocks, the second starting another."""

    BLOCKS = ("Do you support an amendment to make a onetime transfer of "
              "the exemption (Effective January 1, 2027)",
              "to a property owned by a person who is at least "
              "sixty-five years of age",
              "Abstract: Something else entirely here",
              "and who qualifies for the special assessment level? "
              "(Effective January 1, 2028) (Adds Article VII)")
    TEXT = " ".join(BLOCKS)

    def test_verbatim_passes_either_way(self):
        q = "Abstract: Something else entirely here"
        self.assertTrue(_card_quote_in(q, self.TEXT, None))
        self.assertTrue(_card_quote_in(q, self.TEXT, self.BLOCKS))

    def test_hyphen_missing_from_the_text(self):
        q = "make a one-time transfer of the exemption"
        self.assertFalse(_card_quote_in(q, self.TEXT, None))
        self.assertTrue(_card_quote_in(q, self.TEXT, self.BLOCKS))

    def test_one_column_break(self):
        q = ("a property owned by a person who is at least sixty-five "
             "years of age and who qualifies for the special assessment "
             "level? (Effective January 1, 2028) (Adds Article VII)")
        self.assertFalse(_card_quote_in(q, self.TEXT, None))
        self.assertTrue(_card_quote_in(q, self.TEXT, self.BLOCKS))

    def test_pieces_must_be_long_enough_and_verbatim(self):
        # a five-word tail is too short to count as a piece
        self.assertFalse(_card_quote_in(
            "who is at least sixty-five years of age (Adds Article VII)",
            self.TEXT, self.BLOCKS))
        self.assertFalse(_card_quote_in(
            "who is at least sixty-five years of age and who does not "
            "qualify for anything at all", self.TEXT, self.BLOCKS))

    def test_pieces_stitched_mid_block_fail(self):
        # each piece is verbatim in the text, but the first does not end
        # its block: one measure's question with another's tail
        self.assertFalse(_card_quote_in(
            "Do you support an amendment to make a onetime transfer of "
            "the exemption (Effective January 1, 2028) (Adds Article VII)",
            self.TEXT, self.BLOCKS))
        # nor does the second start its block
        self.assertFalse(_card_quote_in(
            "to a property owned by a person who is at least sixty-five "
            "years of age special assessment level? (Effective January 1, "
            "2028)", self.TEXT, self.BLOCKS))


@unittest.skipIf(shutil.which("pdftotext") is None, "needs pdftotext")
class LouisianaStatementsStitchTest(unittest.TestCase):
    """On Louisiana's real one-sheet statements, the one column break a
    card needs passes, and quotes stitched from two amendments fail."""

    def quote_in(self, value):
        from pathlib import Path

        from ballotreels.checks import _archived_blocks, _archived_text
        path = Path("data/la-2026-11-03/amendment-1/sources/"
                    "statements-of-proposed-amendments.pdf").resolve()
        return _card_quote_in(value, _archived_text(path),
                              _archived_blocks(path))

    def test_amendment_6_question_across_its_column_break(self):
        self.assertTrue(self.quote_in(
            "Do you support an amendment to authorize parishes and "
            "municipalities to extend an additional property tax exemption "
            "for property subject to the homestead exemption that is owned "
            "and occupied by a person who is at least sixty-five years of "
            "age and who qualifies for the special assessment level? "
            "(Effective January 1, 2028) (Adds Article VII, Section 21(P))"))

    def test_amendment_1_question_with_amendment_6_tail(self):
        self.assertFalse(self.quote_in(
            "Do you support an amendment to allow the surviving spouse of a "
            "deceased veteran with a service-connected disability, who "
            "receives the additional property tax exemption, to make a "
            "one-time transfer of the additional property tax exemption to "
            "a subsequent qualifying property? (Effective January 1, 2028) "
            "(Adds Article VII, Section 21(P))"))

    def test_amendment_5_summary_with_amendment_8_question(self):
        self.assertFalse(self.quote_in(
            "Proposed Constitutional Amendment removes the requirement that "
            "a statewide retirement system apply nonrecurring monies "
            "received to its oldest unfunded accrued liability first. Do "
            "you support an amendment to prohibit expropriation of property "
            "by a foreign adversary or an agent of a foreign adversary?"))

    def test_alabama_uses_its_ballot_statements_words(self):
        al = BALLOTS["al"]
        self.assertEqual((al.guide, al.fiscal_label, al.choices,
                          al.card_source_kind),
                         ("Fair Ballot Commission Ballot Statement", None,
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(al, "Statewide Amendment 1: X", "1"),
                         "AMENDMENT")

    def test_north_carolina_uses_its_explanations_words(self):
        nc = BALLOTS["nc"]
        self.assertEqual((nc.guide, nc.fiscal_label, nc.choices,
                          nc.card_source_kind),
                         ("Official Summary Explanation", None,
                          ("For", "Against"), "official-title-summary"))

    def test_nebraska_uses_its_pamphlets_words(self):
        ne = BALLOTS["ne"]
        self.assertEqual((ne.fiscal_label, ne.choices, ne.card_source_kind),
                         (None, ("For", "Against"), "official-title-summary"))
        # "INITIATIVE MEASURE 440", as the pamphlet prints it
        self.assertEqual(badge(ne, "Initiative Measure 440: X", "440"),
                         "INITIATIVE MEASURE")
        self.assertEqual(badge(ne, "Proposed Amendment No. 1: X", "1"),
                         "AMENDMENT")
        # the pamphlet covers only the initiatives
        self.assertTrue(guide_of(ne, "ne-2026-11-03-initiative-440")
                        .startswith("Informational Pamphlet"))
        self.assertEqual(guide_of(ne, "ne-2026-11-03-amendment-1"),
                         "Legislative Resolution 19CA")

    def test_indiana_uses_its_election_summarys_words(self):
        in_ = BALLOTS["in"]
        self.assertEqual((in_.guide, in_.fiscal_label, in_.choices,
                          in_.card_source_kind),
                         ("2026 Indiana Election Legislation Summary", None,
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(in_, "Public Question 1: X", "1"),
                         "QUESTION")


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

    def test_colorado_uses_yes_for_and_no_against(self):
        self.edit("sources.toml", "state:ca", "state:co")
        self.set_headings("Why some vote yes/for", "Why some vote no/against")
        self.assertEqual(self.failures(), [])

    def test_colorado_fails_a_word_of_another_states(self):
        self.edit("sources.toml", "state:ca", "state:co")
        self.set_headings("Why some vote yes", "Why some vote no/against")
        self.assertEqual(self.failures(), [
            "[side-heading] yes: heading 'Why some vote yes' says 'yes'; the "
            "ballot's word for this side is 'Yes/For'"])


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
