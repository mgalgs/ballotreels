"""checks.check_chart_precision: a chart must not print a value at a
different precision from the figure its own line says for it. Butte
County's Measure Q printed 33.64 while the line said "33.6 million", and
an operator fixed the value by hand."""

import unittest
from pathlib import Path

from ballotreels import printed
from ballotreels.checks import check_chart_precision, check_contest
from ballotreels.contest import load_contest
from ballotreels.standard import REPO_ROOT

from .helpers import ContestCopyTestCase, unlinted_standard

# Prop 2's one bars chart, and the line it is on (change.line[0]).
LINE = ("Proposition 2 raises the target from 10 to 20 percent of General "
        "Fund taxes.")
VALUES = "values = [10, 20]"

# Committed contests this check refuses, reported to the operator rather
# than edited here (the handoff's rule: no data edits in a code round).
# Remove each as its data is fixed; the test fails if one starts passing,
# so the list only shrinks.
KNOWN: set[str] = set()


class ChartPrecisionTest(ContestCopyTestCase):
    def chart(self, text, values):
        self.edit("script.toml", LINE, text)
        self.edit("script.toml", VALUES, f"values = {values}")
        return check_chart_precision(load_contest(self.dir))

    def test_refuses_a_value_printed_finer_than_it_is_said(self):
        [f] = self.chart("Proposition 2 raises the target from 10 to 33.6 "
                         "percent of General Fund taxes.", "[10, 33.635]")
        self.assertEqual((f.check, f.section, f.line),
                         ("chart-precision", "change", 0))
        self.assertIn("33.635", f.message)
        self.assertIn(repr(printed.with_unit(33.635, "%")), f.message)
        self.assertIn("'33.6'", f.message)
        self.assertIn("make the value 33.6", f.message)

    def test_with_a_scale_word_and_money(self):
        [f] = self.chart("It would cost $33.6 million.", "[10, 33.64]")
        self.assertIn("'33.64%'", f.message)
        self.assertIn("'33.6'", f.message)

    def test_is_part_of_check_contest(self):
        self.chart("Proposition 2 raises the target from 10 to 33.6 percent "
                   "of General Fund taxes.", "[10, 33.635]")
        got = [f for f in check_contest(load_contest(self.dir),
                                        unlinted_standard())
               if f.check == "chart-precision"]
        self.assertEqual(len(got), 1, [str(f) for f in got])

    def test_a_value_said_exactly_passes(self):
        self.assertEqual(self.chart(
            "Proposition 2 raises the target from 10 to 33.6 percent of "
            "General Fund taxes.", "[10, 33.6]"), [])

    def test_a_value_said_exactly_with_a_thousands_comma_passes(self):
        self.assertEqual(self.chart("It rises to 1,500.", "[10, 1500]"), [])

    def test_a_value_the_line_does_not_say_passes(self):
        self.assertEqual(self.chart(LINE, "[10, 33.635]"), [])

    def test_a_figure_another_bar_prints_exactly_is_that_bar_s(self):
        # 19.6 rounds to 20, but the line's 20 is the other bar's
        self.assertEqual(self.chart(LINE, "[19.6, 20]"), [])

    def test_a_one_digit_figure_is_too_coarse_to_match(self):
        # "Proposition 2" is not 2.25 rounded
        self.assertEqual(self.chart(LINE, "[10, 2.25]"), [])

    def test_a_sales_tax_rate_s_three_decimals_print(self):
        self.assertEqual(self.chart(
            "The rate would rise from 10 to 8.375 percent.", "[10, 8.375]"),
            [])

    def test_more_decimals_said_than_the_chart_prints(self):
        [f] = self.chart("The rate would rise from 10 to 8.3755 percent.",
                         "[10, 8.3755]")
        self.assertIn("'8.3755'", f.message)
        self.assertIn("at most three decimals", f.message)

    def test_a_line_that_approximates_passes(self):
        self.assertEqual(self.chart(
            "About 63 percent would go to Muni, and 29 percent to BART.",
            "[62.87, 29.14]"), [])

    def test_a_series_prints_only_its_last_value(self):
        self.edit("script.toml", 'kind = "bars"', 'kind = "series"')
        self.assertEqual(self.chart(
            "From 33.6 percent it rose to 20.", "[33.635, 20]"), [])
        self.edit("script.toml", "values = [33.635, 20]",
                  "values = [20, 33.635]")
        self.edit("script.toml", "From 33.6 percent it rose to 20.",
                  "It rose to 33.6 percent.")
        [f] = check_chart_precision(load_contest(self.dir))
        self.assertIn("33.635", f.message)


class FilmPrintsWithTheSameFunctionsTest(unittest.TestCase):
    def test_the_film_uses_ballotreels_printed(self):
        from film import measure
        self.assertIs(measure.number, printed.number)
        self.assertIs(measure.with_unit, printed.with_unit)


class CommittedContestsTest(unittest.TestCase):
    def test_every_committed_contest(self):
        refused = {}
        for script in sorted((REPO_ROOT / "data").glob("*/*/script.toml")):
            failures = check_chart_precision(load_contest(script.parent))
            if failures:
                name = script.parent.relative_to(REPO_ROOT / "data")
                refused[Path(name).as_posix()] = [str(f) for f in failures]
        self.assertEqual({k: v for k, v in refused.items()
                          if k not in KNOWN}, {})
        self.assertEqual(sorted(KNOWN - set(refused)), [],
                         "fixed: remove from KNOWN")


if __name__ == "__main__":
    unittest.main()
