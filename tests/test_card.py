"""The `[card]` table and the `page` visual (docs/SCRIPT-FORMAT.md), on a
copy of Prop 2 given a card quoting its Quick Reference page."""

import unittest

from ballotreels import check_contest, load_contest
from ballotreels.checks import plain_text

from .helpers import ContestCopyTestCase

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
        return [str(f) for f in check_contest(load_contest(self.dir))]

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

    def test_every_key_required(self):
        for key in ("source", "number", "title", "origin", "summary", "yes",
                    "no"):
            with self.subTest(key=key):
                text = (self.dir / "script.toml").read_text()
                start = text.index(f"\n{key} = ", text.index("[card]"))
                end = text.index("\n", start + 1)
                (self.dir / "script.toml").write_text(text[:start]
                                                      + text[end:])
                got = self.failures()
                self.assertIn(f"[card] has no {key!r}", got)
                (self.dir / "script.toml").write_text(text)

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
            "'official-fiscal-analysis'; a card quotes a source of kind "
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


if __name__ == "__main__":
    unittest.main()
