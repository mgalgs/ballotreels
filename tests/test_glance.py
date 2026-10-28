"""The "ballot at a glance" figures (data/<election>/glance.toml): the
loader, the check, the check command, and the data files themselves."""

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from ballotreels.cli import main
from ballotreels.glance import (GlanceError, check_glance, dollar_figures,
                                load_glance)
from ballotreels.index import load_index

from .helpers import PROP_2, REPO

DATA = REPO / "data"
# The elections whose measures are scripted; MA, CO and NV are being
# scripted now and get their glance.toml later.
LIVE = ("ca", "ut", "wa", "az", "id", "dc", "fl", "oh", "mt")

CONTESTS = """\
[election]
id = "ca-2026-11-03"
state = "ocd-division/country:us/state:ca"
title = "California General Election, November 3, 2026"

[[contest]]
id = "ca-2026-11-03-prop-2"
kind = "measure"
division = "ocd-division/country:us/state:ca"
title = "Proposition 2: Increases State's Rainy Day Fund. Legislative Constitutional Amendment."
number = "2"
"""

NOTE = ("<html><body><p>FISCAL NOTE The measure’s cost would be "
        "$1.5 million to $2.7 billion over ten years, or “about” "
        "$314,000 a year in admin­istration.</p></body></html>")

GOOD = """\
[prop-2]
source = "note"
quote = "The measure's cost would be $1.5 million to $2.7 billion over ten years"
amount = 2700000000
period = "over 10 years"
direction = "cost"
"""


class GlanceTestCase(unittest.TestCase):
    """A scratch election holding a copy of Prop 2, with one extra
    fiscal-analysis source (sources/note.html) to quote figures from."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.election = Path(tmp.name) / "ca-2026-11-03"
        contest = self.election / "prop-2"
        shutil.copytree(PROP_2, contest)
        (self.election / "contests.toml").write_text(CONTESTS,
                                                     encoding="utf-8")
        (contest / "sources" / "note.html").write_text(NOTE,
                                                       encoding="utf-8")
        with (contest / "sources.toml").open("a", encoding="utf-8") as f:
            f.write('\n[[source]]\nid = "note"\n'
                    'kind = "official-fiscal-analysis"\npublisher = "x"\n'
                    'url = "https://example.org/note"\n'
                    'file = "sources/note.html"\nretrieved = "2026-10-27"\n')

    def write(self, text):
        (self.election / "glance.toml").write_text(text, encoding="utf-8")

    def failures(self, text):
        self.write(text)
        return [str(f) for f in check_glance(self.election)]


class DollarFiguresTest(unittest.TestCase):
    def test_figures(self):
        self.assertEqual(
            dollar_figures("$500 million to $600 Million annually"),
            [500_000_000, 600_000_000])
        self.assertEqual(dollar_figures("cost $314,000 over -$11.86 billion"),
                         [314_000, 11_860_000_000])
        self.assertEqual(dollar_figures("not more than $200,000.00."),
                         [200_000])
        self.assertEqual(dollar_figures("$2.7 billion; $5 to $15 billion"),
                         [2_700_000_000, 5, 15_000_000_000])

    def test_words_are_not_figures(self):
        self.assertEqual(dollar_figures(
            "tens of millions of dollars, under 1 billion"), [])


class LoaderTest(GlanceTestCase):
    def test_no_file(self):
        self.assertIsNone(load_glance(self.election))
        self.assertIsNone(check_glance(self.election))

    def test_entry(self):
        self.write(GOOD)
        entry = load_glance(self.election)["prop-2"]
        self.assertEqual((entry.source, entry.amount, entry.period,
                          entry.direction, entry.status),
                         ("note", 2_700_000_000, "over 10 years", "cost",
                          None))

    def test_shape_errors(self):
        cases = {
            "exactly one": '[prop-2]\nsource = "note"\nquote = "x"\n',
            "exactly one ": GOOD + 'status = "not-determined"\n',
            "needs 'source'": '[prop-2]\nstatus = "none-printed"\n',
            "unknown key": GOOD + 'figure = 1\n',
            "whole number": GOOD.replace("2700000000", "2.7e9"),
            "above zero": GOOD.replace("2700000000", "0"),
            "needs its 'period'": GOOD.replace(
                'period = "over 10 years"\n', ""),
            "'period' must be": GOOD.replace("over 10 years", "yearly"),
            "over N years": GOOD.replace("over 10 years", "over 1 years"),
            "'direction' must": GOOD.replace('"cost"', '"spending"'),
            "'status' must": '[prop-2]\nsource = "note"\nstatus = "tbd"\n',
            "needs the 'quote' that says so":
                '[prop-2]\nsource = "note"\nstatus = "not-determined"\n',
            "with an 'amount' only":
                '[prop-2]\nsource = "note"\nstatus = "none-printed"\n'
                'period = "per-year"\n',
            "needs the 'quote' that states it":
                '[prop-2]\nsource = "note"\namount = 5\nperiod = "unstated"\n',
            "must be a table": 'prop-2 = "note"\n',
        }
        for message, text in cases.items():
            with self.subTest(message):
                self.write(text)
                with self.assertRaisesRegex(GlanceError, message.strip()):
                    load_glance(self.election)
                # the check reports the same, as one failure
                self.assertEqual(len(check_glance(self.election)), 1)

    def test_periods(self):
        for period in ("per-year", "one-time", "unstated", "over 4 years",
                       "every 2 years", "over 25 years"):
            with self.subTest(period):
                self.write(GOOD.replace("over 10 years", period))
                self.assertEqual(
                    load_glance(self.election)["prop-2"].period, period)


class CheckTest(GlanceTestCase):
    def test_passes(self):
        self.assertEqual(self.failures(GOOD), [])

    def test_loose_comparison(self):
        # Straight quotes for curly, a soft hyphen in the source, and a
        # hyphen the source does not print all match.
        self.assertEqual(self.failures(
            '[prop-2]\nsource = "note"\n'
            'quote = "or \\"about\\" $314,000 a year in admin-istration."\n'
            'amount = 314000\nperiod = "per-year"\n'), [])

    def test_statuses(self):
        self.assertEqual(self.failures(
            '[prop-2]\nsource = "title-summary"\nstatus = "none-printed"\n'
            'quote = "State budget reserves would be higher."\n'), [])
        self.assertEqual(self.failures(
            '[prop-2]\nsource = "guide-section"\nstatus = "none-printed"\n'),
            [])

    def test_missing_and_unknown_measures(self):
        self.assertEqual(
            self.failures(GOOD.replace("[prop-2]", "[prop-9]")),
            ["[glance] prop-2: measure has no entry",
             "[glance] prop-9: is not a measure in contests.toml"])

    def test_source(self):
        self.assertEqual(
            self.failures(GOOD.replace('"note"', '"nope"')),
            ["[glance] prop-2: source 'nope' is not in its sources.toml"])
        failures = self.failures(GOOD.replace('"note"', '"arguments"'))
        self.assertEqual(len(failures), 1)
        self.assertIn("is 'official-argument', not a fiscal statement",
                      failures[0])

    def test_quote_not_verbatim(self):
        failures = self.failures(GOOD.replace("would be", "will be"))
        self.assertEqual(len(failures), 1)
        self.assertIn("quote does not appear verbatim in source 'note'",
                      failures[0])

    def test_amount_must_be_the_largest_figure(self):
        self.assertEqual(
            self.failures(GOOD.replace("2700000000", "2600000000")),
            ["[glance] prop-2: amount 2600000000 is not a dollar figure the "
             "quote prints ([1500000, 2700000000])"])
        self.assertEqual(
            self.failures(GOOD.replace("2700000000", "1500000")),
            ["[glance] prop-2: amount 1500000 is not the quote's largest "
             "dollar figure (2700000000)"])

    def test_none_printed_with_a_figure_fails(self):
        failures = self.failures(
            '[prop-2]\nsource = "note"\nstatus = "none-printed"\n'
            'quote = "$314,000 a year"\n')
        self.assertEqual(len(failures), 1)
        self.assertIn("give the largest as 'amount'", failures[0])


class CommandTest(GlanceTestCase):
    def run_check(self):
        out = io.StringIO()
        code = main(["check", str(self.election / "prop-2")], out=out)
        return code, out.getvalue().splitlines()

    def test_pass_line(self):
        self.write(GOOD)
        code, lines = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(lines[-1], "PASS glance ca-2026-11-03")

    def test_failure_fails_the_command(self):
        self.write(GOOD.replace("would be", "will be"))
        code, lines = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], "FAIL glance ca-2026-11-03: 1 failure")
        self.assertIn("[glance] prop-2: quote does not appear", lines[-2])


class DataFileTest(unittest.TestCase):
    def test_every_live_election_has_one(self):
        for state in LIVE:
            with self.subTest(state):
                self.assertTrue(
                    (DATA / f"{state}-2026-11-03" / "glance.toml").is_file())

    def test_every_file_passes(self):
        for path in sorted(DATA.glob("*/glance.toml")):
            with self.subTest(path.parent.name):
                self.assertEqual(
                    [str(f) for f in check_glance(path.parent)], [])
                measures = [e for e in load_index(path.parent).entries
                            if e.kind == "measure"]
                self.assertEqual(len(load_glance(path.parent)),
                                 len(measures))


if __name__ == "__main__":
    unittest.main()
