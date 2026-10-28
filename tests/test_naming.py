"""STANDARD.md section 9's machine check (checks.check_naming): every name
a line says is declared, with a role, from a cited record of an allowed
kind that has it verbatim; never in the opening line or a vote line; as
many per side."""

import re
import unittest
from pathlib import Path

from ballotreels import load_contest, load_standard
from ballotreels.checks import check_naming, proper_runs

from .helpers import ContestCopyTestCase

STANDARD = load_standard()
REPO = Path(__file__).resolve().parent.parent

# A background line of the Prop 2 copy, to say a name in.
BACKGROUND_LINE = ('text = "In 2014, voters approved the rules the state '
                   'follows today."\nsources = ["lao-volatility"]')
FILING = ('<html><body><p>The proponent of the measure is Jane Roe.</p>'
          '</body></html>')


class NamingTest(ContestCopyTestCase):
    def naming(self):
        return check_naming(load_contest(self.dir), STANDARD.proper_words)

    def add_filing(self, kind="election-filing"):
        (self.dir / "sources" / "filing.html").write_text(FILING,
                                                          encoding="utf-8")
        with (self.dir / "sources.toml").open("a", encoding="utf-8") as f:
            f.write('\n[[source]]\nid = "filing"\n'
                    f'kind = "{kind}"\n'
                    'publisher = "Secretary of State"\n'
                    'url = "https://example.gov/filing"\n'
                    'file = "sources/filing.html"\n'
                    'retrieved = "2026-10-27"\n')

    def say_in_background(self, text, name="Jane Roe", role="its proponent",
                          source="filing", cites='"lao-volatility", "filing"'):
        names = "" if name is None else (
            f'\nnames = [{{ name = "{name}", role = "{role}", '
            f'source = "{source}" }}]')
        self.edit("script.toml", BACKGROUND_LINE,
                  f'text = "{text}"\nsources = [{cites}]{names}')

    def test_fixture_passes(self):
        # The copy's side lines name the organisations whose leaders signed
        # each argument, three a side, each declared from the arguments.
        self.assertEqual(self.naming(), [])

    def test_declared_name_from_a_filing_passes(self):
        self.add_filing()
        self.say_in_background("Jane Roe, its proponent, filed it in 2014.")
        self.assertEqual(self.naming(), [])

    def test_undeclared_name(self):
        self.say_in_background("Governor Gavin Newsom signed it in 2014.",
                               name=None, cites='"lao-volatility"')
        [f] = self.naming()
        self.assertEqual((f.section, f.line), ("background[3]", 1))
        self.assertIn("'Governor Gavin Newsom'", f.message)
        self.assertIn("declare it", f.message)

    def test_name_not_verbatim_in_its_source(self):
        self.add_filing()
        self.say_in_background("Jane Doe, its proponent, filed it in 2014.",
                               name="Jane Doe")
        [f] = self.naming()
        self.assertIn("'Jane Doe' does not appear verbatim in 'filing'",
                      f.message)

    def test_source_of_a_disallowed_kind(self):
        self.add_filing(kind="official-title-summary")
        self.say_in_background("Jane Roe, its proponent, filed it in 2014.")
        [f] = self.naming()
        self.assertIn("of kind 'official-title-summary'", f.message)
        self.assertIn("rule 9.1", f.message)

    def test_source_the_line_does_not_cite(self):
        self.add_filing()
        self.say_in_background("Jane Roe, its proponent, filed it in 2014.",
                               cites='"lao-volatility"')
        [f] = self.naming()
        self.assertIn("which the line does not cite", f.message)

    def test_name_or_role_the_line_does_not_say(self):
        self.add_filing()
        self.say_in_background("Jane Roe filed it in 2014.")
        [f] = self.naming()
        self.assertIn("the line does not say that role", f.message)

    def test_missing_field(self):
        self.say_in_background("The rules date from 2014.", role="")
        [f] = self.naming()
        self.assertIn("needs a non-empty role", f.message)

    def test_name_in_the_opening_line(self):
        self.add_filing()
        self.edit("script.toml",
                  'text = "Proposition 2 is about California\'s savings '
                  'account for hard times: the Rainy Day Fund."\n'
                  'sources = ["title-summary", "lao-analysis"]',
                  'text = "Proposition 2, from Jane Roe, its proponent, is '
                  'about the Rainy Day Fund."\n'
                  'sources = ["title-summary", "lao-analysis", "filing"]\n'
                  'names = [{ name = "Jane Roe", role = "its proponent", '
                  'source = "filing" }]')
        [f] = self.naming()
        self.assertEqual((f.section, f.line), ("what", 0))
        self.assertIn("in the opening line", f.message)

    def test_declared_name_in_a_vote_line(self):
        self.edit("script.toml",
                  'text = "A no vote means the current rules would not '
                  'change."',
                  'text = "A no vote means Reform California\'s rules stay."')
        got = [f for f in self.naming() if f.section == "vote"]
        self.assertTrue(any("'Reform California' in a vote line" in f.message
                            for f in got), [str(f) for f in got])

    def test_name_outside_background_and_sides(self):
        self.add_filing()
        self.edit("script.toml",
                  'text = "Today, the state has about 20 billion dollars in '
                  'reserves it can use for any program."\n'
                  'sources = ["lao-analysis"]',
                  'text = "Jane Roe, its proponent, filed it."\n'
                  'sources = ["lao-analysis", "filing"]\n'
                  'names = [{ name = "Jane Roe", role = "its proponent", '
                  'source = "filing" }]')
        [f] = self.naming()
        self.assertEqual(f.section, "today")
        self.assertIn("rule 9.5", f.message)

    def test_unequal_per_side(self):
        # The run "Assembly Budget Committee" is all known words, so only
        # the count fails when its declaration is dropped.
        self.edit("script.toml",
                  '  { name = "Assembly Budget Committee", role = "signed by '
                  'leaders of", source = "arguments" },\n  { name = "Senate',
                  '  { name = "Senate')
        [f] = self.naming()
        self.assertIn("yes=3, no=2", f.message)
        self.assertIn("rule 9.3", f.message)

    def test_unfiled_side_is_not_counted(self):
        self.edit("script.toml",
                  '  { name = "Assembly Budget Committee", role = "signed by '
                  'leaders of", source = "arguments" },\n  { name = "Senate',
                  '  { name = "Senate')
        self.edit("script.toml", 'side = "no"\n', 'side = "no"\nfiled = false\n')
        self.assertEqual(self.naming(), [])


class ProperRunsTest(unittest.TestCase):
    def runs(self, text):
        return [[w for w, _ in run] for _, run in proper_runs(text)]

    def test_runs_break_at_punctuation_and_lower_case(self):
        self.assertEqual(
            self.runs("Supporters, including Senator Lincoln Fillmore, the "
                      "Utah Senate's sponsor, say so."),
            [["Senator", "Lincoln", "Fillmore"], ["Utah", "Senate"]])

    def test_sentence_opener_is_marked(self):
        [(_, run)] = proper_runs("It passed. In Utah the vote held.")
        self.assertEqual(run, [("In", True), ("Utah", False)])

    def test_opener_alone_does_not_hide_a_name(self):
        # "Governor" opens the sentence, but "Newsom" is still checked.
        [(_, run)] = proper_runs("Governor Newsom signed it.")
        self.assertEqual([w for w, _ in run], ["Governor", "Newsom"])


class CommittedContestsTest(unittest.TestCase):
    def test_every_committed_contest_passes(self):
        # No false positive on any committed script, and the pilots'
        # declared names check out.
        for script in sorted(REPO.glob("data/*/*/script.toml")):
            c = load_contest(script.parent)
            self.assertEqual(
                [str(f) for f in check_naming(c, STANDARD.proper_words)], [],
                c.id)


class ProperWordsListTest(unittest.TestCase):
    def test_list_is_single_capitalised_words(self):
        for w in STANDARD.proper_words:
            self.assertRegex(w, r"^[A-Z][A-Za-z]*$")
            self.assertFalse(re.search(r"\s", w))


if __name__ == "__main__":
    unittest.main()
