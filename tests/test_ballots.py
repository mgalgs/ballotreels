"""Each state's ballot wording (ballotreels.ballots), and the checks that
hold a script to its own state's words."""

import shutil
import unittest

from ballotreels import check_contest, load_contest
from ballotreels.ballots import BALLOTS, badge, ballot_for, designation
from ballotreels.checks import _card_quote_in, _in_text

from ballotreels.ballots import (BALLOTS, badge, ballot_for, designation,
                                 guide_of)

from .helpers import ContestCopyTestCase, unlinted_standard
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
                             for s, b in BALLOTS.items()
                             if s not in ("la", "nh")))


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


class CardStraysTest(unittest.TestCase):
    """Text pdftotext sets inside a card's quote (a document footer, the
    ballot's Yes and No boxes) is dropped only as whole words, and only
    for the contests that name it."""

    def test_named_only_for_two_san_bernardino_cards_benicia_z_and_j(self):
        self.assertEqual(sorted(BALLOTS["ca"].card_strays),
                         ["ca-2026-11-03-benicia-measure-z",
                          "ca-2026-11-03-california-city-measure-j",
                          "ca-2026-11-03-grand-terrace-measure-n",
                          "ca-2026-11-03-needles-measure-l"])
        self.assertFalse(any(b.card_strays for s, b in BALLOTS.items()
                             if s not in ("ca", "tn")))

    def test_dropped_as_whole_words(self):
        from ballotreels.checks import _without_strays
        text = "emergency response, Yes and rapid. Resolution No. 2026-21"
        self.assertEqual(_without_strays(text, ("Yes", "No")),
                         "emergency response, and rapid. "
                         "Resolution No. 2026-21")
        self.assertEqual(_without_strays("Yesterday No", ("Yes",)),
                         "Yesterday No")


@unittest.skipIf(shutil.which("pdftotext") is None, "needs pdftotext")
class SanBernardinoCardStraysTest(unittest.TestCase):
    """On the real resolution and ordinance, the ballot question is a
    verbatim card quote once its strays are dropped, and not before."""

    def test_question_needs_its_strays_dropped(self):
        from pathlib import Path

        from ballotreels.checks import _archived_text, _without_strays
        for slug, pdf, quote in (
                ("grand-terrace-measure-n", "RES_GT.pdf",
                 "9-1-1 emergency response, and rapid response times"),
                ("needles-measure-l", "FT_CityofNeedles.pdf",
                 "generating on average $739,971 annually"),
                # the question's bullets, read as an "x" each
                ("benicia-measure-z", "resolution-and-full-text.pdf",
                 "rates of 0.004 for sales $2,000,000 or less, 0.006"),
                # the resolution's YES and NO boxes, set beside the question
                ("california-city-measure-j", "county-resolution.pdf",
                 "amend the transient occupancy tax provisions")):
            text = _archived_text(Path(
                f"data/ca-2026-11-03/{slug}/sources/{pdf}").resolve())
            strays = BALLOTS["ca"].card_strays[f"ca-2026-11-03-{slug}"]
            self.assertNotIn(quote, text)
            self.assertIn(quote, _without_strays(text, strays))


class TennesseeCardStraysTest(unittest.TestCase):
    """On the Secretary of State's page, each amendment's "As proposed by"
    line is a verbatim card quote once the snapshot's bracketed link
    targets are dropped, and not before; only its own are dropped."""

    def test_origin_needs_its_link_targets_dropped(self):
        from pathlib import Path

        from ballotreels.checks import _archived_text, _without_strays
        for n, first, second in (
                (1, "SENATE JOINT RESOLUTION NO. 919 (113th)",
                 "SENATE JOINT RESOLUTION 25 (114th)"),
                (2, "HOUSE JOINT RESOLUTION NO. 81 (113th)",
                 "SENATE JOINT RESOLUTION 1 (114th)"),
                (3, "HOUSE JOINT RESOLUTION NO. 94 (113th)",
                 "SENATE JOINT RESOLUTION 9 (114th)")):
            text = _archived_text(Path(
                f"data/tn-2026-11-03/amendment-{n}/sources/"
                f"sos-2026-proposed-amendments-page.txt").resolve())
            strays = BALLOTS["tn"].card_strays[
                f"tn-2026-11-03-amendment-{n}"]
            quote = f"As proposed by {first} & {second}"
            self.assertNotIn(quote, text)
            self.assertIn(quote, _without_strays(text, strays))


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

    def test_west_virginia_uses_its_notices_words(self):
        wv = BALLOTS["wv"]
        self.assertEqual((wv.guide, wv.fiscal_label, wv.choices,
                          wv.card_source_kind),
                         ("Public Notice", None,
                          ("For", "Against"), "official-title-summary"))
        # "Amendment No. 1: Citizenship Requirement ...", as the ballot heads it
        self.assertEqual(badge(wv, "Amendment No. 1: X", "1"), "AMENDMENT")

    def test_kansas_uses_its_ballots_words(self):
        ks = BALLOTS["ks"]
        self.assertEqual((ks.guide, ks.fiscal_label, ks.choices,
                          ks.card_source_kind),
                         ("Official General Election Ballot", None,
                          ("Yes", "No"), "official-title-summary"))

    def test_kentucky_uses_its_ballots_words(self):
        ky = BALLOTS["ky"]
        self.assertEqual((ky.guide, ky.fiscal_label, ky.choices,
                          ky.card_source_kind),
                         ("Sample Ballot", None, ("Yes", "No"),
                          "official-title-summary"))
        self.assertEqual(badge(ky, "Constitutional Amendment 1: X", "1"),
                         "AMENDMENT")

    def test_indiana_uses_its_election_summarys_words(self):
        in_ = BALLOTS["in"]
        self.assertEqual((in_.guide, in_.fiscal_label, in_.choices,
                          in_.card_source_kind),
                         ("2026 Indiana Election Legislation Summary", None,
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(in_, "Public Question 1: X", "1"),
                         "QUESTION")

    def test_vermont_uses_its_ballots_words(self):
        vt = BALLOTS["vt"]
        self.assertEqual((vt.guide, vt.fiscal_label, vt.choices,
                          vt.card_source_kind),
                         ("Official State Constitutional Amendment Ballot",
                          None, ("Yes", "No"), "official-title-summary"))
        # "PROPOSAL 3", as the ballot prints it
        self.assertEqual(badge(vt, "Proposal 3: X", "3"), "PROPOSAL")

    def test_wisconsin_uses_its_notices_words(self):
        wi = BALLOTS["wi"]
        self.assertEqual((wi.guide, wi.fiscal_label, wi.choices,
                          wi.card_source_kind),
                         ("Type A Notice of Referendum", None, ("Yes", "No"),
                          "official-title-summary"))
        # "QUESTION 1", as the notice prints it
        self.assertEqual(badge(wi, "Question 1: Partial veto", "1"),
                         "QUESTION")

    def test_minnesota_uses_its_secretary_of_states_words(self):
        mn = BALLOTS["mn"]
        self.assertEqual((mn.guide, mn.fiscal_label, mn.choices,
                          mn.card_source_kind),
                         ("Constitutional amendments", None,
                          ("Yes", "No"), "official-title-summary"))

    def test_missouri_uses_its_ballot_measures_pages_words(self):
        mo = BALLOTS["mo"]
        self.assertEqual((mo.guide, mo.fiscal_label, mo.choices,
                          mo.card_source_kind),
                         ("2026 Ballot Measures", "Fiscal Note Summary",
                          ("Yes", "No"), "official-title-summary"))
        self.assertEqual(badge(mo, "Amendment 3: X", "3"), "AMENDMENT")
        self.assertEqual(badge(mo, "Proposition A: X", "A"), "PROPOSITION")

    def test_tennessee_uses_its_secretary_of_states_words(self):
        tn = BALLOTS["tn"]
        self.assertEqual((tn.guide, tn.fiscal_label, tn.choices,
                          tn.card_source_kind),
                         ("2026 Proposed Constitutional Amendments",
                          "FISCAL IMPACT:", ("Yes", "No"),
                          "official-title-summary"))
        # "Constitutional Amendment #1", the "#" dropped from the title
        self.assertEqual(badge(tn, "Constitutional Amendment 1: X", "1"),
                         "AMENDMENT")

    def test_michigan_uses_its_ballot_questions_words(self):
        mi = BALLOTS["mi"]
        self.assertEqual((mi.guide, mi.fiscal_label, mi.choices,
                          mi.card_source_kind),
                         ("2026 November ballot questions", "Fiscal Impact",
                          ("Yes", "No"), "official-title-summary"))
        # "Proposal 26-1", as the fiscal agencies print it
        self.assertEqual(badge(mi, "Proposal 26-1: X", "26-1"), "PROPOSAL")

    def test_new_hampshire_uses_its_secretary_of_states_words(self):
        nh = BALLOTS["nh"]
        self.assertEqual((nh.guide, nh.fiscal_label, nh.choices,
                          nh.card_source_kind, nh.card_column_breaks),
                         ("Questions on the General Election Ballot 2026",
                          None, ("Yes", "No"), "official-title-summary",
                          True))
        # "Question 2", with the title's designation as its badge
        self.assertEqual(
            badge(nh, "Question 2: School district property tax limits",
                  "2"),
            "QUESTION")

    def test_oklahoma_uses_its_final_ballot_titles_words(self):
        ok = BALLOTS["ok"]
        self.assertEqual((ok.guide, ok.fiscal_label, ok.choices,
                          ok.card_source_kind),
                         ("Final Ballot Title", None, ("Yes", "No"),
                          "official-title-summary"))
        # "STATE QUESTION 845", as the State Election Board heads it
        self.assertEqual(badge(ok, "State Question 845: X", "845"),
                         "STATE QUESTION")

    def test_iowa_uses_its_sample_ballots_words(self):
        ia = BALLOTS["ia"]
        self.assertEqual((ia.guide, ia.fiscal_label, ia.choices,
                          ia.card_source_kind),
                         ("Sample Ballot", None, ("Yes", "No"),
                          "official-title-summary"))
        # "Statewide Public Measure 1", as the ballot heads it
        self.assertEqual(badge(ia, "Public Measure 1: X", "1"),
                         "PUBLIC MEASURE")

    def test_alaska_uses_its_election_pamphlets_words(self):
        ak = BALLOTS["ak"]
        self.assertEqual((ak.guide, ak.fiscal_label, ak.choices,
                          ak.card_source_kind, ak.card_column_breaks),
                         ("Official Election Pamphlet", "Statement of Costs",
                          ("Yes", "No"), "official-title-summary", False))
        # "Ballot Measure No. 2", whose designation word is "Measure"
        self.assertEqual(badge(ak, "Ballot Measure 2: X", "2"),
                         "BALLOT MEASURE")

    def test_south_dakota_uses_its_pamphlets_words(self):
        sd = BALLOTS["sd"]
        self.assertEqual((sd.guide, sd.fiscal_label, sd.choices,
                          sd.card_source_kind),
                         ("2026 Ballot Question Pamphlet", None,
                          ("Yes", "No"), "official-title-summary"))
        # "Constitutional Amendment I", as the pamphlet heads it
        self.assertEqual(
            badge(sd, "Constitutional Amendment I: Medicaid expansion", "I"),
            "AMENDMENT")


class SideHeadingTest(ContestCopyTestCase):
    def failures(self):
        return [str(f) for f in check_contest(load_contest(self.dir),
                                              unlinted_standard())]

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


class WrappedHyphenTest(unittest.TestCase):
    """A plain-text copy that wraps a hyphenated word after its hyphen
    ("well-" / "trained") keeps the hyphen and gains a space; a card
    quoting the word as printed still matches (checks._in_text)."""

    TEXT = ("recruit/retain well- trained firefighters; shall the measure "
            "levy a tax, with low- income senior exemption, be adopted?")

    def test_wrapped_hyphenated_word_matches(self):
        self.assertTrue(_in_text("recruit/retain well-trained firefighters",
                                 self.TEXT))
        self.assertTrue(_in_text("with low-income senior exemption",
                                 self.TEXT))

    def test_other_words_still_verbatim(self):
        self.assertFalse(_in_text("recruit/retain well-paid firefighters",
                                  self.TEXT))
        self.assertFalse(_in_text("welltrained firefighters", self.TEXT))
