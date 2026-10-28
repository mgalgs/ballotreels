"""Each machine check, failing on a deliberately broken copy of Prop 2."""

import re
import unittest

from ballotreels import check_contest, load_contest, load_standard
from ballotreels.standard import (REPO_ROOT, SOURCE_KINDS,
                                  judgment_word_pattern, read_judgment_words)

from .helpers import PROP_2, ContestCopyTestCase, drop_background, write_narration


class Prop2PassesTest(unittest.TestCase):
    def test_passes_every_check(self):
        # Its two sides' spoken durations differ by 1.4s, within the 2s
        # pad cap, so check_airtime's padded layout now covers it.
        self.assertEqual(check_contest(load_contest(PROP_2)), [])


class BrokenCopyTest(ContestCopyTestCase):
    def failures(self):
        return check_contest(load_contest(self.dir))

    def assertOnly(self, check, section=None, line=None, count=1):
        """The copy fails exactly `count` times, all on `check` there."""
        got = self.failures()
        self.assertEqual(len(got), count, [str(f) for f in got])
        for f in got:
            self.assertEqual((f.check, f.section, f.line),
                             (check, section, line), str(f))
        return got

    # 1. contest id
    def test_contest_id_mismatch(self):
        self.edit("script.toml", 'contest = "ca-2026-11-03-prop-2"',
                  'contest = "ca-2026-11-03-prop-3"')
        self.assertOnly("contest-id")

    # 2. sources xor connective
    def test_line_with_neither(self):
        self.edit("script.toml",
                  'connective = true', 'connective = false')
        self.assertOnly("line-citation", "vote", 2)

    def test_line_with_empty_sources(self):
        self.edit("script.toml", 'sources = ["guide-section", "lao-analysis"]'
                  '\n\n[[section]]\nid = "background"',
                  'sources = []\n\n[[section]]\nid = "background"')
        [f] = self.assertOnly("line-citation", "what", 1)
        self.assertIn("empty", f.message)

    def test_line_with_both(self):
        self.edit("script.toml", 'sources = ["quick-reference"]\n\n'
                  '[[section.line]]\ntext = "Every fact',
                  'sources = ["quick-reference"]\n\n'
                  '[[section.line]]\nsources = ["guide-section"]\n'
                  'text = "Every fact')
        self.assertOnly("line-citation", "vote", 2)

    # 3. cited sources exist
    def test_unknown_cited_source(self):
        self.edit("script.toml", 'sources = ["title-summary", "lao-analysis"]',
                  'sources = ["title-summary", "news-story"]')
        [f] = self.assertOnly("cited-source", "what", 0)
        self.assertIn("news-story", f.message)

    # 4. source kinds and files
    def test_disallowed_source_kind(self):
        self.edit("sources.toml", 'kind = "official-text"',
                  'kind = "newspaper-editorial"')
        [f] = self.assertOnly("source")
        self.assertIn("newspaper-editorial", f.message)

    def test_missing_source_file(self):
        (self.dir / "sources" / "analysis.html").unlink()
        [f] = self.assertOnly("source")
        self.assertIn("lao-analysis", f.message)

    def test_source_file_outside_contest(self):
        (self.dir.parent / "elsewhere.html").write_text("x")
        self.edit("sources.toml", 'file = "sources/analysis.html"',
                  'file = "../elsewhere.html"')
        [f] = self.assertOnly("source")
        self.assertIn("outside", f.message)

    # 4b. background-only kinds (rule 6.1)
    TODAY_RESERVES = ('text = "Today, the state has about 20 billion dollars '
                      'in reserves it can use for any program."\n'
                      'sources = ["lao-analysis"]')

    def test_official_report_outside_background(self):
        self.edit("script.toml", self.TODAY_RESERVES,
                  self.TODAY_RESERVES.replace('"lao-analysis"',
                                              '"lao-analysis", '
                                              '"lao-volatility"'))
        [f] = self.assertOnly("background-only", "today", 3)
        self.assertIn("lao-volatility", f.message)

    def test_official_data_outside_background(self):
        self.edit("sources.toml", 'kind = "official-report"',
                  'kind = "official-data"')
        self.assertEqual(self.failures(), [])  # all its uses are background
        self.edit("script.toml", self.TODAY_RESERVES,
                  self.TODAY_RESERVES.replace('"lao-analysis"',
                                              '"lao-volatility"'))
        [f] = self.assertOnly("background-only", "today", 3)
        self.assertIn("'official-data'", f.message)

    FISCAL_LINE = ('somewhat easier when revenue falls."\n'
                   'sources = ["lao-analysis"]')

    def test_official_report_beside_the_fiscal_analysis(self):
        # rule 6.5: the budget total that gives a fiscal figure its scale
        self.edit("script.toml", self.FISCAL_LINE,
                  self.FISCAL_LINE.replace('"lao-analysis"',
                                           '"lao-analysis", '
                                           '"lao-volatility"'))
        self.assertEqual(self.failures(), [])

    def test_official_report_alone_on_a_fiscal_line(self):
        self.edit("script.toml", self.FISCAL_LINE,
                  self.FISCAL_LINE.replace('"lao-analysis"',
                                           '"lao-volatility"'))
        self.assertOnly("background-only", "fiscal", 0)

    def test_background_failures_name_the_section(self):
        # Prop 2 has four background sections; the third is labelled
        # background[2].
        self.edit("script.toml", "trade-off: money that is saved",
                  "bold trade-off: money that is saved")
        self.assertOnly("judgment-word", "background[2]", 2)

    # 4c. charts (docs/SCRIPT-FORMAT.md, rule 7.1)
    def assertVisual(self, section, line, *messages):
        """The copy fails only on its chart there, once per message, each
        failure's message containing the matching entry."""
        got = self.assertOnly("visual", section, line, count=len(messages))
        for f, want in zip(got, messages):
            self.assertIn(want, f.message)

    def test_bars_negative_value(self):
        self.edit("script.toml", "values = [10, 20]", "values = [10, -1]")
        self.assertVisual("change", 0, "values must be >= 0")

    def test_series_allows_negative_values(self):
        self.edit("script.toml", 'kind = "bars"', 'kind = "series"')
        self.edit("script.toml", 'labels = ["Today", "Proposition 2"]',
                  'labels = ["2024", "2026"]')
        self.edit("script.toml", "values = [10, 20]", "values = [-10, 20]")
        self.assertEqual(self.failures(), [])

    def test_series_years_evenly_spaced(self):
        self.edit("script.toml", 'kind = "bars"', 'kind = "series"')
        self.assertVisual("change", 0, "labels must be years")
        self.edit("script.toml", 'labels = ["Today", "Proposition 2"]',
                  'labels = ["2020", "2021", "2023"]')
        self.edit("script.toml", "values = [10, 20]", "values = [1, 2, 3]")
        self.assertVisual("change", 0, "must increase evenly")

    def test_labels_and_values_differ_in_length(self):
        self.edit("script.toml", "values = [10, 20]", "values = [10, 20, 30]")
        self.assertVisual("change", 0, "has 2 labels but 3 values")

    def test_values_must_be_numbers(self):
        self.edit("script.toml", "values = [10, 20]", 'values = ["10", 20]')
        self.assertVisual("change", 0, "'values' must be a list of numbers")

    def test_bars_missing_and_forbidden_fields(self):
        self.edit("script.toml", 'unit = "%"\nlabels = ["Today"',
                  'figure = "jar"\nlabels = ["Today"')
        self.edit("script.toml",
                  'title = "Rainy Day Fund target, as a share of General '
                  'Fund taxes"\n', '')
        self.assertVisual("change", 0, "has no 'title'",
                          "may not have 'figure'", "has no 'unit'")

    def test_unknown_kind(self):
        self.edit("script.toml", 'kind = "bars"', 'kind = "pie"')
        self.assertVisual("change", 0, "kind 'pie' is not one of")

    def test_share_sums_to_at_most_100(self):
        self.edit("script.toml", "values = [50, 33, 17]",
                  "values = [33.3, 33.3, 33.4]")
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "values = [33.3, 33.3, 33.4]",
                  "values = [50, 33, 27]")
        self.assertVisual("background[0]", 1, "sum to 110, more than 100")

    def test_figure_fields(self):
        self.edit("script.toml",
                  'figure = "steady-spending-volatile-revenue"\n',
                  'labels = ["a"]\nvalues = [1]\nunit = ""\n')
        self.assertVisual("background[1]", 3, "has no 'figure'",
                          "may not have 'labels'", "may not have 'values'",
                          "may not have 'unit'")

    def test_chart_source_not_among_line_sources(self):
        self.edit("script.toml", 'source = "lao-analysis"\nunit = "%"\n'
                  'labels = ["Today"', 'source = "title-summary"\n'
                  'unit = "%"\nlabels = ["Today"')
        self.assertVisual("change", 0, "not among the line's sources")

    def test_chart_source_unknown(self):
        self.edit("script.toml", 'source = "lao-analysis"\nunit = "%"\n'
                  'labels = ["Today"', 'source = "news-story"\n'
                  'unit = "%"\nlabels = ["Today"')
        self.assertVisual("change", 0, "'news-story', which is not in "
                          "sources.toml")

    def test_chart_source_disallowed_kind(self):
        with open(self.dir / "sources.toml", "a", encoding="utf-8") as f:
            f.write('\n[[source]]\nid = "poll"\nkind = "opinion-poll"\n'
                    'publisher = "x"\nurl = "x"\n'
                    'file = "sources/analysis.html"\nretrieved = "x"\n')
        self.edit("script.toml", 'from 10 to 20 percent of General Fund '
                  'taxes. The state would keep saving until the fund reaches '
                  'it."\nsources = ["lao-analysis"]',
                  'from 10 to 20 percent of General Fund taxes. The state '
                  'would keep saving until the fund reaches it."\n'
                  'sources = ["lao-analysis", "poll"]')
        self.edit("script.toml", 'source = "lao-analysis"\nunit = "%"\n'
                  'labels = ["Today"', 'source = "poll"\n'
                  'unit = "%"\nlabels = ["Today"')
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("visual", "change", 0), ("source", None, None)])
        self.assertIn("'opinion-poll', which is not an allowed kind",
                      got[0].message)

    def test_chart_background_only_source_outside_background(self):
        self.edit("script.toml", 'from 10 to 20 percent of General Fund '
                  'taxes. The state would keep saving until the fund reaches '
                  'it."\nsources = ["lao-analysis"]',
                  'from 10 to 20 percent of General Fund taxes. The state '
                  'would keep saving until the fund reaches it."\n'
                  'sources = ["lao-analysis", "lao-volatility"]')
        self.edit("script.toml", 'source = "lao-analysis"\nunit = "%"\n'
                  'labels = ["Today"', 'source = "lao-volatility"\n'
                  'unit = "%"\nlabels = ["Today"')
        got = self.assertOnly("background-only", "change", 0, count=2)
        self.assertTrue(got[0].message.startswith("cites"))
        self.assertTrue(got[1].message.startswith("has a chart citing"))

    # 4d. charts in side sections (rule 7.3)
    # Each side's first line, through its basis: a visual added after it
    # must come after every key of the line.
    SIDE_LINE = {"yes": 'next downturn."\nsources = ["arguments"]\n'
                        'basis = ["Proposition 2 strengthens that fund, so '
                        'schools, healthcare, and public safety don\'t pay '
                        'the price for Sacramento\'s boom-and-bust '
                        'budgeting."]',
                 "no": 'less likely."\nsources = ["arguments"]\n'
                       'basis = ["In 1978 California voters overwhelmingly '
                       'voted to amend the state constitution to impose a '
                       'spending limit on state politicians", "while making '
                       'it less likely that taxpayers will receive the '
                       'rebates they are constitutionally owed"]'}

    def add_side_chart(self, side, kind):
        chart = (f'\n\n[section.line.visual]\nkind = "{kind}"\n'
                 f'title = "x"\nsource = "arguments"\n')
        chart += ('figure = "jar"\n' if kind == "figure" else
                  'unit = ""\nlabels = ["a"]\nvalues = [1]\n')
        self.edit("script.toml", self.SIDE_LINE[side],
                  self.SIDE_LINE[side] + chart)

    def test_chart_on_one_side(self):
        self.add_side_chart("yes", "bars")
        [f] = self.assertOnly("side-visual", "yes", 0)
        self.assertIn("one 'list' visual and no other", f.message)

    def test_charts_of_same_kinds_on_both_sides(self):
        # matched, but the shared sides slide draws only a list, so a chart
        # in a side would pass and then never be shown
        self.add_side_chart("yes", "bars")
        self.add_side_chart("no", "bars")
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("side-visual", "yes", 0), ("side-visual", "no", 0)])
        self.assertIn("this is a 'bars'", got[0].message)

    def test_charts_of_different_kinds_on_the_sides(self):
        self.add_side_chart("yes", "bars")
        self.add_side_chart("no", "figure")
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("side-visual", "yes", 0), ("side-visual", "no", 0)])

    # 4e. timelines and illustrations (docs/SCRIPT-FORMAT.md)
    TODAY_LINE = ('deposits stop, and that money goes to infrastructure, like '
                  'highways and housing, instead."\nsources = ["lao-analysis"]')

    def add_visual(self, body, after=None):
        """Give the `today` section's line[1] (or the line ending `after`) a
        visual with TOML `body`."""
        after = after or self.TODAY_LINE
        self.edit("script.toml", after,
                  after + "\n\n[section.line.visual]\n" + body)

    ILLUSTRATION = 'kind = "illustration"\nname = "save-more"\n'
    TIMELINE = ('kind = "timeline"\nsource = "lao-analysis"\n'
                'labels = ["2014", "2030"]\nitems = ["Rules set", "Ends"]\n')

    def test_well_formed_new_visuals(self):
        self.add_visual(self.ILLUSTRATION)
        self.add_visual(self.TIMELINE, after='for any program."\n'
                        'sources = ["lao-analysis"]')
        self.assertEqual(self.failures(), [])

    def test_every_library_entry_is_usable(self):
        from ballotreels.illustrations import load_library
        library = load_library()
        self.assertGreaterEqual(len(library), 10)
        for entry in library.values():
            self.assertTrue(entry.path.is_file(), entry.file)

    def test_illustration_not_in_the_library(self):
        self.add_visual(self.ILLUSTRATION.replace("save-more", "a-cat"))
        self.assertVisual("today", 1, "names 'a-cat', which is not in "
                          "film/illustrations/illustrations.toml")

    def test_illustration_file_missing(self):
        from unittest import mock

        from ballotreels.illustrations import Illustration
        missing = {"save-more": Illustration("save-more", "nowhere.png", "")}
        self.add_visual(self.ILLUSTRATION)
        with mock.patch("ballotreels.checks.load_library",
                        return_value=missing):
            self.assertVisual("today", 1, "whose file 'nowhere.png' does "
                              "not exist")

    def test_illustration_needs_a_name(self):
        self.add_visual('kind = "illustration"\n')
        self.assertVisual("today", 1, "has no 'name'")

    def test_illustration_has_no_source_or_title(self):
        self.add_visual(self.ILLUSTRATION + 'source = "lao-analysis"\n'
                        'title = "Saving"\n')
        self.assertVisual("today", 1, "may not have 'title'",
                          "may not have 'source'")

    def test_illustration_stamp(self):
        self.add_visual(self.ILLUSTRATION + 'stamp = "None reported"\n')
        self.assertEqual(self.failures(), [])

    def test_stamp_must_be_short_words_on_one_line(self):
        for stamp, want in (('""', "'stamp' must be a non-empty string"),
                            ('"  "', "'stamp' must be a non-empty string"),
                            ("3", "'stamp' must be a non-empty string"),
                            ('"None\\nreported"', "'stamp' must be one line"),
                            ('"' + "x" * 25 + '"',
                             "'stamp' is 25 characters, more than 24")):
            with self.subTest(stamp=stamp):
                self.setUp()
                self.add_visual(self.ILLUSTRATION + f"stamp = {stamp}\n")
                self.assertVisual("today", 1, want)

    def test_only_an_illustration_has_a_stamp(self):
        self.add_visual(self.TIMELINE + 'stamp = "None reported"\n')
        self.assertVisual("today", 1, "may not have 'stamp'")

    def test_judgment_word_in_a_stamp(self):
        self.add_visual(self.ILLUSTRATION + 'stamp = "Sweeping"\n')
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line, f.message)
                          for f in got],
                         [("judgment-word", "today", 1,
                           "judgment word 'Sweeping' in visual stamp")])

    def test_words_and_number_are_gone(self):
        self.add_visual('kind = "words"\ntext = "deposits stop"\n')
        self.add_visual('kind = "number"\ntext = "10%"\nlabel = "target"\n'
                        'source = "lao-analysis"\n',
                        after='for any program."\nsources = ["lao-analysis"]')
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("visual", "today", 1), ("visual", "today", 3)])
        self.assertTrue(got[0].message.startswith("'words' visual only "
                                                  "shows text"))
        self.assertTrue(got[1].message.startswith("'number' visual only "
                                                  "shows text"))
        for f in got:
            self.assertIn("use an 'illustration' or a chart instead",
                          f.message)

    def test_timeline_labels_and_items_match(self):
        self.add_visual(self.TIMELINE.replace('"Ends"]', '"Ends", "x"]'))
        self.assertVisual("today", 1, "has 2 labels but 3 items")

    def test_timeline_at_least_two_entries(self):
        self.add_visual(self.TIMELINE.replace('["2014", "2030"]', '["2014"]')
                        .replace(', "Ends"]', ']'))
        self.assertVisual("today", 1, "at least 2 entries")

    def test_timeline_items_are_strings(self):
        self.add_visual(self.TIMELINE.replace('"Ends"]', '3]'))
        self.assertVisual("today", 1, "'items' must be a list of strings")

    def test_one_part_share(self):
        self.add_visual('kind = "share"\ntitle = "Rainy Day Fund target"\n'
                        'source = "lao-analysis"\nunit = "%"\n'
                        'labels = ["Rainy Day Fund target"]\nvalues = [10]\n')
        self.assertEqual(self.failures(), [])

    def test_judgment_words_on_screen(self):
        self.add_visual(self.TIMELINE.replace('"Ends"', '"Sweeping end"'),
                        after='for any program."\n'
                        'sources = ["lao-analysis"]')
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line, f.message)
                          for f in got],
                         [("judgment-word", "today", 3,
                           "judgment word 'Sweeping' in visual items")])

    def add_side_illustration(self, side, name):
        self.edit("script.toml", self.SIDE_LINE[side],
                  self.SIDE_LINE[side]
                  + f'\n\n[section.line.visual]\nkind = "illustration"\n'
                    f'name = "{name}"\n')

    def test_illustration_on_one_side(self):
        self.add_side_illustration("yes", "save-more")
        [f] = self.assertOnly("side-visual", "yes", 0)
        self.assertIn("this is a 'illustration'", f.message)

    def test_illustrations_on_both_sides(self):
        self.add_side_illustration("yes", "save-more")
        self.add_side_illustration("no", "spending-limit")
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("side-visual", "yes", 0), ("side-visual", "no", 0)])

    def test_timeline_on_one_side(self):
        self.edit("script.toml", self.SIDE_LINE["no"],
                  self.SIDE_LINE["no"] + '\n\n[section.line.visual]\n'
                  + self.TIMELINE.replace("lao-analysis", "arguments"))
        [f] = self.assertOnly("side-visual", "no", 0)
        self.assertIn("this is a 'timeline'", f.message)

    # 4f. the 'list' visual (docs/SCRIPT-FORMAT.md; rule 7.3)
    def add_side_list(self, side, items):
        body = ", ".join(f'"{x}"' for x in items)
        self.edit("script.toml", self.SIDE_LINE[side],
                  self.SIDE_LINE[side] + '\n\n[section.line.visual]\n'
                  f'kind = "list"\nsource = "arguments"\nitems = [{body}]\n')

    LIST_YES = ["Protects schools, health care and public safety in downturns",
               "Stops overspending when there is a surplus"]
    LIST_NO = ["Weakens the spending limit and makes tax rebates less likely",
              "Adds no new money for schools, health care or public safety"]
    LIST = 'kind = "list"\nsource = "lao-analysis"\nitems = ["Rules set", "Ends"]\n'

    def test_well_formed_list(self):
        self.add_visual(self.LIST)
        self.assertEqual(self.failures(), [])

    def test_list_needs_at_least_one_item(self):
        self.add_visual(self.LIST.replace('items = ["Rules set", "Ends"]',
                                          'items = []'))
        self.assertVisual("today", 1, "needs at least 1 item")

    def test_list_judgment_word_in_item_fails(self):
        self.add_visual(self.LIST.replace("Ends", "Sweeping end"))
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line, f.message)
                          for f in got],
                         [("judgment-word", "today", 1,
                           "judgment word 'Sweeping' in visual items")])

    def test_list_equal_item_counts_on_both_sides_passes(self):
        self.add_side_list("yes", self.LIST_YES)
        self.add_side_list("no", self.LIST_NO)
        self.assertEqual(self.failures(), [])

    def test_list_unequal_item_counts_fail_naming_both_counts(self):
        self.add_side_list("yes", self.LIST_YES)
        self.add_side_list("no", self.LIST_NO[:1])
        [f] = self.assertOnly("side-list-items")
        self.assertIn("yes section's 'list' has 2 items", f.message)
        self.assertIn("no section's has 1", f.message)

    def test_list_counts_not_compared_when_a_side_filed_nothing(self):
        self.edit("script.toml", 'side = "no"', 'side = "no"\nfiled = false')
        self.add_side_list("yes", self.LIST_YES)
        self.add_side_list("no", ["No argument against was submitted"])
        self.assertEqual(self.failures(), [])

    def test_both_sides_may_have_filed_nothing(self):
        # A state that publishes no official arguments (DC, Florida): each
        # side says so once, with its one-item list, and nothing fails.
        self.edit("script.toml", 'side = "yes"', 'side = "yes"\nfiled = false')
        self.edit("script.toml", 'side = "no"', 'side = "no"\nfiled = false')
        self.add_side_list("yes", ["No official argument for was published"])
        self.add_side_list("no", ["No official argument against was published"])
        self.assertEqual(self.failures(), [])

    def test_list_on_one_side_fails(self):
        self.add_side_list("yes", self.LIST_YES)
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("side-visual", "yes", 0),
                          ("side-list-items", None, None)])

    def test_judgment_word_in_list_item_fails(self):
        self.add_side_list("yes", ["Stops wasteful overspending"])
        self.add_side_list("no", self.LIST_NO[:1])
        [f] = self.assertOnly("judgment-word", "yes", 0)
        self.assertIn("judgment word 'wasteful' in visual items", f.message)

    # 5. template
    def test_unknown_template(self):
        self.edit("script.toml", 'template = "measure"', 'template = "race"')
        self.assertOnly("template")

    def test_unknown_template_version(self):
        self.edit("script.toml", "template_version = 2",
                  "template_version = 3")
        self.assertOnly("template")

    def test_sections_out_of_order(self):
        self.edit("script.toml", 'id = "today"', 'id = "TMP"')
        self.edit("script.toml", 'id = "change"', 'id = "today"')
        self.edit("script.toml", 'id = "TMP"', 'id = "change"')
        [f] = self.assertOnly("template")
        self.assertIn("background, change, today", f.message)
        self.assertIn("requires what, background*, today", f.message)

    def test_background_after_today(self):
        self.edit("script.toml",
                  'id = "background"\nheading = "How we got here"',
                  'id = "today"\nheading = "How we got here"')
        self.edit("script.toml",
                  'id = "today"\nheading = "The rules today"',
                  'id = "background"\nheading = "The rules today"')
        got = self.failures()
        # The moved section's lines cite a background-only source, now
        # outside a background section.
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("background-only", "today", 0),
                          ("background-only", "today", 1),
                          ("template", None, None)])

    def test_no_background_sections(self):
        drop_background(self.dir)
        self.assertEqual(self.failures(), [])

    def test_version_1_script(self):
        # A template 1 script loads and is checked; under Standard 2 it
        # fails only the standard-version check.
        drop_background(self.dir)
        self.edit("script.toml", "template_version = 2",
                  "template_version = 1")
        self.edit("script.toml", "standard_version = 2",
                  "standard_version = 1")
        self.assertOnly("standard-version")

    def test_background_in_version_1_script(self):
        self.edit("script.toml", "template_version = 2",
                  "template_version = 1")
        [f] = self.assertOnly("template")
        self.assertIn("v1 requires what, today, change", f.message)

    def test_missing_side(self):
        self.edit("script.toml", 'side = "no"\n', '')
        self.assertOnly("template", "no")

    def test_side_on_non_side_section(self):
        self.edit("script.toml", 'heading = "What it is"',
                  'heading = "What it is"\nside = "yes"')
        # Two yes sides also leave nothing for side parity to compare.
        self.assertOnly("template", "what")

    def test_sides_swapped(self):
        self.edit("script.toml", 'side = "yes"', 'side = "TMP"')
        self.edit("script.toml", 'side = "no"', 'side = "yes"')
        self.edit("script.toml", 'side = "TMP"', 'side = "no"')
        got = self.failures()
        self.assertEqual({(f.check, f.section) for f in got},
                         {("template", "yes"), ("template", "no")})

    # 6. side parity
    def test_side_parity(self):
        self.edit("script.toml", 'text = "And they say its backers soon '
                  'voted to suspend over 5 billion dollars in deposits."',
                  'text = "And they say its backers voted."')
        # Nine words shorter is short in spoken time too, and the copy
        # has no narration yet, so the estimate (check_spoken_parity) says
        # so beside the word count.
        got = self.failures()
        self.assertEqual(sorted(f.check for f in got),
                         ["side-parity", "spoken-parity"], [str(f) for f in got])
        [f] = [f for f in got if f.check == "side-parity"]
        self.assertIn("yes=79, no=70", f.message)

    def test_side_parity_boundary(self):
        # yes has 79 words; 5% of 79 is 3.95, so no may be 76 but not 75.
        self.edit("script.toml", "soon voted to suspend over 5 billion",
                  "voted to suspend billion")
        self.assertEqual(self.failures(), [])
        self.edit("script.toml", "voted to suspend billion",
                  "voted to suspend")
        [f] = self.assertOnly("side-parity")
        self.assertIn("yes=79, no=75", f.message)

    # 7. judgment words
    def test_judgment_word_in_text(self):
        self.edit("script.toml", "The Legislature put it",
                  "The Legislature, in a FAIR process, put it")
        [f] = self.assertOnly("judgment-word", "what", 1)
        self.assertIn("'FAIR'", f.message)

    def test_judgment_word_in_heading(self):
        self.edit("script.toml", 'heading = "Fiscal effect"',
                  'heading = "Sweeping fiscal effect"')
        self.assertOnly("judgment-word", "fiscal")

    def test_judgment_multiword_and_hyphenated(self):
        self.edit("script.toml", "Proposition 2 is about",
                  "Proposition 2 is a common-sense change about")
        self.edit("script.toml", "The Legislature put it",
                  "In common\tsense terms, the Legislature put it")
        got = self.failures()
        self.assertEqual(
            sorted((f.section, f.line, f.message) for f in got),
            [("what", 0, "judgment word 'common-sense' in text"),
             ("what", 1, "judgment word 'common\\tsense' in text")])

    def test_judgment_word_not_inside_other_words(self):
        self.edit("script.toml", "The Legislature put it",
                  "The Legislature, a boldface affair, put it")
        self.assertEqual(self.failures(), [])

    # 8. standard version
    def test_standard_version(self):
        self.edit("script.toml", "standard_version = 2",
                  "standard_version = 0")
        self.assertOnly("standard-version")

    # 9. airtime
    def test_airtime_balanced(self):
        write_narration(self.dir)
        self.assertEqual(self.failures(), [])

    def test_airtime_within_the_pad_cap_passes(self):
        # Shrinking "no" by 3% (32.35s -> ~31.4s) is a 0.95s gap, well
        # within the 2s cap: padded, not failed.
        write_narration(self.dir, stretch={"no": 0.97})
        self.assertEqual(self.failures(), [])

    def test_airtime_imbalance(self):
        # Both sides have 79 words in 4 one-sentence lines: 32.35s each at
        # the stand-in narration's pace. Shrinking "no" by 10% makes it
        # 29.19s, a 3.16s gap: past the 2s pad cap.
        write_narration(self.dir, stretch={"no": 0.9})
        [f] = self.assertOnly("airtime")
        self.assertRegex(f.message, r"yes=32\.\ds, no=29\.2s")

    def test_airtime_pads_any_gap_when_a_side_filed_nothing(self):
        # The same 3.16s gap passes when the short side filed no argument:
        # its one line saying so can't be as long as the other side's case.
        write_narration(self.dir, stretch={"no": 0.9})
        self.edit("script.toml", 'side = "no"\n', 'side = "no"\nfiled = false\n')
        self.assertNotIn("airtime", {f.check for f in self.failures()})

    def test_airtime_pads_any_gap_when_both_sides_filed_nothing(self):
        write_narration(self.dir, stretch={"no": 0.9})
        self.edit("script.toml", 'side = "yes"\n', 'side = "yes"\nfiled = false\n')
        self.edit("script.toml", 'side = "no"\n', 'side = "no"\nfiled = false\n')
        self.assertNotIn("airtime", {f.check for f in self.failures()})

    def test_airtime_skips_when_narration_is_stale(self):
        # "bold" is also a judgment word, so the edit still fails a check,
        # just not "airtime": the sidecars no longer match this line's text,
        # so airtime can't be measured from them and says nothing.
        write_narration(self.dir, stretch={"no": 0.9})
        self.edit("script.toml", "The Legislature put it",
                  "The Legislature, in a bold process, put it")
        self.assertEqual({f.check for f in self.failures()}, {"judgment-word"})

    def test_airtime_skips_with_no_sidecars(self):
        self.assertFalse((self.dir / "narration.json").exists())
        self.assertEqual(self.failures(), [])

    def test_reports_every_failure(self):
        self.edit("script.toml", 'contest = "ca-2026-11-03-prop-2"',
                  'contest = "x"')
        self.edit("script.toml", "standard_version = 2",
                  "standard_version = 0")
        self.edit("script.toml", "The Legislature put it",
                  "The bold Legislature put it")
        self.assertEqual([f.check for f in self.failures()],
                         ["contest-id", "judgment-word", "standard-version"])


class StandardTest(unittest.TestCase):
    def test_version_comes_from_standard_md(self):
        text = (REPO_ROOT / "docs" / "STANDARD.md").read_text()
        self.assertTrue(text.rstrip().endswith(
            f"Standard version: {load_standard().version}"))

    def test_judgment_words_skip_comments_and_blanks(self):
        words = read_judgment_words(REPO_ROOT / "standard" /
                                    "judgment-words.txt")
        self.assertIn("common sense", words)
        self.assertIn("fair", words)
        self.assertFalse(any(w.startswith("#") or not w for w in words))

    def test_pattern_boundaries(self):
        p = judgment_word_pattern(("fair", "common sense"))
        self.assertTrue(p.search("a Fair deal"))
        self.assertTrue(p.search("fair-minded"))
        self.assertFalse(p.search("an affair"))
        self.assertFalse(p.search("unfair"))
        self.assertTrue(p.search("Common\nSense."))
        self.assertFalse(p.search("commonsense"))

    def test_source_kinds_match_format_doc(self):
        doc = (REPO_ROOT / "docs" / "SCRIPT-FORMAT.md").read_text()
        para = doc.split("Allowed source kinds", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(set(re.findall(r"`([a-z-]+)`", para)), SOURCE_KINDS)


if __name__ == "__main__":
    unittest.main()
