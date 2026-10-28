"""The `[card]` table and the `page` visual (docs/SCRIPT-FORMAT.md), on a
copy of Prop 2 given a card quoting its Quick Reference page."""

import shutil
import unittest
from pathlib import Path

from ballotreels import check_contest, load_contest
from ballotreels.checks import (_archived_text, _in_raw_columns, _unshifted,
                                plain_text)

from .helpers import ContestCopyTestCase, unlinted_standard

TITLE = ("INCREASES STATE’S RAINY DAY FUND. LEGISLATIVE CONSTITUTIONAL "
         "AMENDMENT.")
CARD = f'''[card]
source = "quick-reference"
number = "2"
title = "{TITLE}"
origin = "Put on the Ballot by the Legislature"
summary = "Increases California's Rainy Day Fund, approved by voters in 2014, to provide funding for education, health care, public safety, and other essential services during economic downturns. Fiscal Impact: State budget reserves would be higher."
yes = "A YES vote on this measure means: Rules for building state budget reserves and paying down extra state debts would change. As a result, state budget reserves would be higher. The state also would be required to make extra debt payments for longer."
no = "A NO vote on this measure means: Rules for building state budget reserves and paying down extra state debts would not change."

'''
VERSION = "standard_version = 2\n\n"
VOTE_YES = ('text = "A yes vote means reserves would be higher, and extra '
            'debt payments would continue for longer."\n'
            'sources = ["quick-reference"]\n')


class CardTest(ContestCopyTestCase):
    def setUp(self):
        super().setUp()
        self.edit("script.toml", VERSION, VERSION + CARD)

    def failures(self):
        return [str(f) for f in check_contest(load_contest(self.dir),
                                              unlinted_standard())]

    def add_page(self, extra="", source="quick-reference"):
        """Give the vote section's first line a `page` visual."""
        self.edit("script.toml", VOTE_YES,
                  VOTE_YES + f'\n[section.line.visual]\nkind = "page"\n'
                             f'source = "{source}"\n{extra}')

    def test_card_passes(self):
        self.assertEqual(self.failures(), [])
        card = load_contest(self.dir).script.card
        self.assertEqual(card.number, "2")
        self.assertEqual(card.title, TITLE)

    def test_no_card(self):
        self.edit("script.toml", CARD, "")
        self.assertIsNone(load_contest(self.dir).script.card)
        self.assertEqual(self.failures(), [])

    def drop_key(self, key):
        text = (self.dir / "script.toml").read_text()
        start = text.index(f"\n{key} = ", text.index("[card]"))
        end = text.index("\n", start + 1)
        (self.dir / "script.toml").write_text(text[:start] + text[end:])
        return text

    def test_every_key_required(self):
        for key in ("source", "title", "origin", "summary"):
            with self.subTest(key=key):
                text = self.drop_key(key)
                got = self.failures()
                self.assertIn(f"[card] has no {key!r}", got)
                (self.dir / "script.toml").write_text(text)

    def test_number_optional(self):
        """A ballot that numbers no measure (North Carolina's) leaves the
        card's number out, and the card draws no badge."""
        self.drop_key("number")
        self.assertEqual(self.failures(), [])
        self.assertIsNone(load_contest(self.dir).script.card.number)

    def test_yes_and_no_together_or_neither(self):
        for key, other in (("yes", "no"), ("no", "yes")):
            with self.subTest(key=key):
                text = self.drop_key(key)
                self.assertEqual(self.failures(), [
                    f"[card] has {other!r} but no {key!r}: the two votes' "
                    f"meanings come together or not at all"])
                (self.dir / "script.toml").write_text(text)
        self.drop_key("yes")
        self.drop_key("no")
        self.assertEqual(self.failures(), [])
        self.assertIsNone(load_contest(self.dir).script.card.yes)

    def test_fiscal_is_quoted_verbatim(self):
        self.edit("script.toml", 'origin = "Put',
                  'fiscal = "State budget reserves would be higher."\n'
                  'origin = "Put')
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "would be higher.\"\norigin",
                  "would be much higher.\"\norigin")
        self.assertEqual(self.failures(), [
            "[card] 'fiscal' does not appear verbatim in source "
            "'quick-reference' (sources/quick-reference.html)"])

    def test_no_fiscal_where_the_guide_prints_none(self):
        self.edit("script.toml", 'origin = "Put',
                  'fiscal = "State budget reserves would be higher."\n'
                  'origin = "Put')
        self.edit("sources.toml", "state:ca", "state:az")
        self.assertEqual(self.failures(), [
            "[card] has a 'fiscal' quote, but the state's guide prints no "
            "fiscal statement to quote"])

    def test_badge_needs_a_designation_in_the_title(self):
        self.edit("sources.toml",
                  'title = "Proposition 2: Increases',
                  'title = "2: Increases')
        self.assertEqual(self.failures(), [
            "[card] the contest title \"2: Increases State's Rainy Day Fund. "
            "Legislative Constitutional Amendment.\" has no designation word "
            "just before the number '2', for the card's badge"])

    def test_a_state_without_ballot_wording_fails(self):
        self.edit("sources.toml", "state:ca", "state:zz")
        self.assertEqual(self.failures(), [
            "[ballot] no ballot wording for the state of "
            "'ocd-division/country:us/state:zz'; add it to "
            "ballotreels/ballots.py"])

    def test_key_must_be_a_string(self):
        self.edit("script.toml", 'number = "2"', "number = 2")
        self.assertEqual(self.failures(),
                         ["[card] 'number' must be a non-empty string"])

    def test_source_must_exist(self):
        self.edit("script.toml", 'source = "quick-reference"\nnumber',
                  'source = "voter-pamphlet"\nnumber')
        self.assertEqual(self.failures(), [
            "[card] source 'voter-pamphlet' is not in sources.toml"])

    def test_source_kind(self):
        self.edit("script.toml", 'source = "quick-reference"\nnumber',
                  'source = "lao-analysis"\nnumber')
        self.assertEqual(self.failures(), [
            "[card] source 'lao-analysis' is of kind "
            "'official-fiscal-analysis'; a card quotes the measure's page "
            "in the Official Voter Information Guide, a source of kind "
            "'official-title-summary'"])

    def test_verbatim_fails_naming_the_field(self):
        self.edit("script.toml", "approved by voters in 2014",
                  "approved by the voters in 2014")
        self.assertEqual(self.failures(), [
            "[card] 'summary' does not appear verbatim in source "
            "'quick-reference' (sources/quick-reference.html)"])

    def test_verbatim_keeps_case_and_quotes(self):
        self.edit("script.toml", "STATE’S", "STATE'S")
        self.edit("script.toml", "A NO vote", "A No vote")
        self.assertEqual(self.failures(), [
            "[card] 'title' does not appear verbatim in source "
            "'quick-reference' (sources/quick-reference.html)",
            "[card] 'no' does not appear verbatim in source "
            "'quick-reference' (sources/quick-reference.html)"])

    def test_verbatim_allows_a_hyphen_joined_at_a_line_break(self):
        # pdftotext joins "eighty-" / "two" into "eightytwo"; the card
        # keeps the hyphen as printed. Nothing else is loosened.
        self.edit("sources/quick-reference.html", "economic downturns",
                  "economicdownturns", count=2)
        self.edit("script.toml", "during economic downturns. Fiscal",
                  "during economic-downturns. Fiscal")
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "economic-downturns", "economic-Downturns")
        self.assertEqual(self.failures(), [
            "[card] 'summary' does not appear verbatim in source "
            "'quick-reference' (sources/quick-reference.html)"])

    def test_a_one_misprinted_for_an_l_may_be_corrected(self):
        # "potentia1" in Alabama's ballot statement for Amendment 2
        self.edit("sources/quick-reference.html", "essential services",
                  "essentia1 services")
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "essential services", "essentia1 services")
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "approved by voters in 2014",
                  "approved by voters in 20l4")
        self.assertEqual(self.failures(), [
            "[card] 'summary' does not appear verbatim in source "
            "'quick-reference' (sources/quick-reference.html)"])

    def test_plain_text(self):
        self.assertEqual(
            plain_text('<head><style>p { x }</style><script>var a = "<b>";'
                       '</script></head><p>Rainy&#44; Day <strong>Fiscal '
                       'Impact</strong>&#58;\n  State &amp; more .</p>'),
            "Rainy, Day Fiscal Impact: State & more.")

    def test_judgment_words_exempt_on_the_card_only(self):
        # The archived page never uses a judgment word, so put one in it.
        self.edit("sources/quick-reference.html", "STATE’S RAINY DAY",
                  "STATE’S BOLD RAINY DAY")
        self.edit("script.toml", "STATE’S RAINY DAY", "STATE’S BOLD RAINY DAY")
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "would not change.\"\nsources",
                  "would not change, a bold step.\"\nsources")
        self.assertEqual(self.failures(), [
            "[judgment-word] vote.line[1]: judgment word 'bold' in text"])

    def test_page_visual(self):
        self.add_page('focus = "vote on this measure means"\n')
        self.assertEqual(self.failures(), [])
        v = load_contest(self.dir).script.sections[-1].lines[0].visual
        self.assertEqual((v.kind, v.focus),
                         ("page", "vote on this measure means"))

    def test_page_without_focus(self):
        self.add_page()
        self.assertEqual(self.failures(), [])

    def test_focus_not_found(self):
        self.add_page('focus = "rainy day fund"\n')  # case matters
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual focus 'rainy day fund' "
            "does not occur in the card's text"])

    def test_page_needs_a_card(self):
        self.add_page()
        self.edit("script.toml", CARD, "")
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual needs a [card] table in "
            "script.toml"])

    def test_page_source_must_be_the_cards(self):
        both = VOTE_YES.replace('["quick-reference"]',
                                '["quick-reference", "title-summary"]')
        self.edit("script.toml", VOTE_YES,
                  both + '\n[section.line.visual]\nkind = "page"\n'
                         'source = "title-summary"\n')
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual cites 'title-summary', but "
            "the card quotes 'quick-reference'"])

    def test_page_source_among_the_lines(self):
        self.edit("script.toml", VOTE_YES,
                  VOTE_YES.replace("quick-reference", "lao-analysis")
                  + '\n[section.line.visual]\nkind = "page"\n'
                    'source = "quick-reference"\n')
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual cites 'quick-reference', "
            "which is not among the line's sources"])

    def test_page_has_no_title(self):
        self.add_page('title = "The page"\n')
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual a 'page' visual may not "
            "have 'title'"])

    def test_focus_only_on_a_page(self):
        self.edit("script.toml", 'kind = "bars"',
                  'kind = "bars"\nfocus = "Rainy Day Fund"')
        got = self.failures()
        self.assertEqual(len(got), 1, got)
        self.assertIn("may not have 'focus'", got[0])

    def test_highlight(self):
        self.add_page('highlight = ["Rainy Day Fund", "economic downturns"]\n')
        self.assertEqual(self.failures(), [])
        v = load_contest(self.dir).script.sections[-1].lines[0].visual
        self.assertEqual(v.highlight, ["Rainy Day Fund", "economic downturns"])

    def test_highlight_passes(self):
        self.add_page('highlight = ["Rainy Day Fund", "during economic '
                      'downturns", "paying down extra state debts"]\n')
        self.assertEqual(self.failures(), [])

    def test_highlight_not_found(self):
        self.add_page('highlight = ["Rainy Day Fund", "rainy day fund"]\n')
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual highlight 'rainy day fund' "
            "does not occur in the card's text"])

    def test_highlight_must_be_a_list_of_strings(self):
        for bad in ('"Rainy Day Fund"', "[]", '[""]', "[2]"):
            with self.subTest(bad=bad):
                text = (self.dir / "script.toml").read_text()
                self.add_page(f"highlight = {bad}\n")
                self.assertEqual(self.failures(), [
                    "[visual] vote.line[0]: 'page' visual 'highlight' must "
                    "be a non-empty list of non-empty strings"])
                (self.dir / "script.toml").write_text(text)

    def test_focus_and_highlight_refused(self):
        self.add_page('focus = "Rainy Day Fund"\n'
                      'highlight = ["during economic downturns"]\n')
        self.assertEqual(self.failures(), [
            "[visual] vote.line[0]: 'page' visual has both 'focus' and "
            "'highlight': a line clicks a term or highlights phrases, not "
            "both"])

    def test_highlight_only_on_a_page(self):
        self.edit("script.toml", 'kind = "bars"',
                  'kind = "bars"\nhighlight = ["Rainy Day Fund"]')
        got = self.failures()
        self.assertEqual(len(got), 1, got)
        self.assertIn("may not have 'highlight'", got[0])

    def test_highlight_balance_fails(self):
        # "would change" is in the YES box, "As a result" too; the NO box has
        # "would not change" only
        self.add_page('highlight = ["would change", "As a result", '
                      '"would not change"]\n')
        self.assertEqual(self.failures(), [
            "[highlight-balance] highlights fall 2 times in the card's YES "
            "box and 1 times in its NO box; they must be equal"])

    def test_highlight_balance_passes(self):
        self.add_page('highlight = ["would change", "would not change"]\n')
        self.assertEqual(self.failures(), [])

    def test_highlight_balance_counts_the_whole_script(self):
        # the YES box's phrase on one line, the NO box's on another
        self.add_page('highlight = ["would change"]\n')
        self.assertEqual(self.failures(), [
            "[highlight-balance] highlights fall 1 times in the card's YES "
            "box and 0 times in its NO box; they must be equal"])
        no_line = ('text = "A no vote means the current rules would not '
                   'change."\nsources = ["quick-reference"]\n')
        self.edit("script.toml", no_line,
                  no_line + '\n[section.line.visual]\nkind = "page"\n'
                            'source = "quick-reference"\n'
                            'highlight = ["would not change"]\n')
        self.assertEqual(self.failures(), [])

    def test_highlight_shared_by_both_boxes_balances_itself(self):
        self.add_page('highlight = ["Rules for building state budget '
                      'reserves", "vote on this measure means"]\n')
        self.assertEqual(self.failures(), [])


if __name__ == "__main__":
    unittest.main()


GA_BOOKLET = (Path(__file__).resolve().parent.parent / "data" /
              "ga-2026-11-03" / "amendment-1" / "sources" /
              "guide-section.pdf")


@unittest.skipUnless(shutil.which("pdftotext"), "needs poppler's pdftotext")
class ColumnTextTest(unittest.TestCase):
    """Georgia's booklet is set in narrow newspaper columns, which
    pdftotext's default reading order interleaves; a card quote is also
    found in the columns read whole, with whitespace ignored."""

    CAPTION = ("Increases the maximum qualifying acreage for assessment "
               "and taxation as bona fide conservation use property.")

    def test_interleaved_columns_defeat_the_default_text(self):
        self.assertNotIn(self.CAPTION, _archived_text(GA_BOOKLET))

    def test_a_quote_is_found_in_the_columns(self):
        self.assertTrue(_in_raw_columns(self.CAPTION, GA_BOOKLET))
        # "ShalltheConstitution" and "acresto4,000acres" in the -raw text
        self.assertTrue(_in_raw_columns(
            "Shall the Constitution of Georgia, for the purpose of "
            "protecting family farmland", GA_BOOKLET))

    def test_the_words_must_still_match(self):
        self.assertFalse(_in_raw_columns(
            "Increases the maximum qualifying acreage for taxation",
            GA_BOOKLET))
        self.assertFalse(_in_raw_columns(
            "This proposal increases the maximum acreage to qualify for "
            "assessment and taxation as a bona fide conservation use "
            "property from 2,000 acres to 5,000 acres.", GA_BOOKLET))


ALAMEDA_GUIDE = (Path(__file__).resolve().parent.parent / "data" /
                 "ca-2026-11-03" / "alameda-county-measure-rtm" / "sources" /
                 "vig-pp758-768.pdf")


class ShiftedGlyphTest(unittest.TestCase):
    """Alameda County's guide sets some lines in a font with no Unicode
    map, which pdftotext prints as glyph indices, each character's code
    less 29; those lines are read decoded."""

    def test_a_shifted_line_is_decoded(self):
        self.assertEqual(_unshifted("x\nWUD\u0d76F\x0f\x03DQG\x03\x14\x17\n"),
                         "x\ntraffic, and 14\n")

    def test_other_lines_and_texts_are_kept(self):
        # a line with a lower-case letter is the font's own text
        self.assertEqual(_unshifted("a \x03b\nDQG\x03"), "a \x03b\nand ")
        # no sign of the font at all: nothing changes, upper case included
        self.assertEqual(_unshifted("BART RTM\fRTM-2\n"), "BART RTM\fRTM-2\n")
        # a Spanish "¿" in a line of ordinary text stays one
        self.assertEqual(_unshifted("¿Qué?\nDQG\x03"), "¿Qué?\nand ")

    @unittest.skipUnless(shutil.which("pdftotext"),
                         "needs poppler's pdftotext")
    def test_the_guide_reads_as_printed(self):
        text = _archived_text(ALAMEDA_GUIDE)
        self.assertIn("traffic, and reduce pollution by: Preserving BART, "
                      "Caltrain, VTA", text)
        self.assertIn("It is estimated that the tax would raise "
                      "approximately $980 million per year.", text)
