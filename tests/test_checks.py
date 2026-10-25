"""Each machine check, failing on a deliberately broken copy of Prop 2."""

import re
import unittest

from ballotreels import check_contest, load_contest, load_standard
from ballotreels.standard import (REPO_ROOT, SOURCE_KINDS,
                                  judgment_word_pattern, read_judgment_words)

from .helpers import (PROP_2, PROP_2_AIRTIME, ContestCopyTestCase,
                      drop_background, write_narration)


class Prop2PassesTest(unittest.TestCase):
    def test_only_the_known_airtime_failure(self):
        self.assertEqual([str(f) for f in check_contest(load_contest(PROP_2))],
                         [PROP_2_AIRTIME])


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
    SIDE_LINE = {"yes": 'next downturn."\nsources = ["arguments"]',
                 "no": 'less likely."\nsources = ["arguments"]'}

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
        self.assertIn("yes has bars, no has none", f.message)

    def test_charts_of_same_kinds_on_both_sides(self):
        self.add_side_chart("yes", "bars")
        self.add_side_chart("no", "bars")
        self.assertEqual(self.failures(), [])

    def test_charts_of_different_kinds_on_the_sides(self):
        self.add_side_chart("yes", "bars")
        self.add_side_chart("no", "figure")
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line) for f in got],
                         [("side-visual", "yes", 0), ("side-visual", "no", 0)])

    # 4e. numbers, words and timelines (docs/SCRIPT-FORMAT.md)
    TODAY_LINE = ('deposits stop, and that money goes to infrastructure, like '
                  'highways and housing, instead."\nsources = ["lao-analysis"]')

    def add_visual(self, body, after=None):
        """Give the `today` section's line[1] (or the line ending `after`) a
        visual with TOML `body`."""
        after = after or self.TODAY_LINE
        self.edit("script.toml", after,
                  after + "\n\n[section.line.visual]\n" + body)

    NUMBER = 'kind = "number"\ntext = "10%"\nlabel = "fund target"\n' \
             'source = "lao-analysis"\n'
    TIMELINE = ('kind = "timeline"\nsource = "lao-analysis"\n'
                'labels = ["2014", "2030"]\nitems = ["Rules set", "Ends"]\n')

    def test_well_formed_new_visuals(self):
        self.add_visual(self.NUMBER)
        self.add_visual('kind = "words"\ntext = "RETIREE HEALTH DEBTS"\n',
                        after='debts, until 2030."\nsources = ["lao-analysis"]')
        self.add_visual(self.TIMELINE, after='for any program."\n'
                        'sources = ["lao-analysis"]')
        self.assertEqual(self.failures(), [])

    def test_number_shows_only_what_the_line_says(self):
        self.add_visual(self.NUMBER.replace('"10%"', '"10.5%"'))
        self.assertVisual("today", 1, "shows '5', which the line's text "
                          "does not say")

    def test_number_digit_runs_match_whole(self):
        # "1" is inside "10" in the text, but is not a number the line says
        self.add_visual(self.NUMBER.replace('"10%"', '"1%"'))
        self.assertVisual("today", 1, "shows '1'")

    def test_number_needs_a_number(self):
        self.add_visual(self.NUMBER.replace('"10%"', '"ten"'))
        self.assertVisual("today", 1, "has no number in it")

    def test_number_label_at_most_six_words(self):
        self.add_visual(self.NUMBER.replace(
            '"fund target"', '"one two three four five six seven"'))
        self.assertVisual("today", 1, "'label' has 7 words, more than 6")

    def test_number_fields(self):
        self.add_visual('kind = "number"\ntext = "10%"\ntitle = "x"\n')
        self.assertVisual("today", 1, "has no 'source'",
                          "may not have 'title'", "has no 'label'")

    def test_number_source_among_line_sources(self):
        self.add_visual(self.NUMBER.replace('"lao-analysis"',
                                            '"title-summary"'))
        self.assertVisual("today", 1, "not among the line's sources")

    def test_words_verbatim_from_the_line(self):
        self.add_visual('kind = "words"\ntext = "deposits halt"\n')
        self.assertVisual("today", 1, "'deposits halt' is not in the line")

    def test_words_at_most_six_words(self):
        self.add_visual('kind = "words"\ntext = "and that money goes to '
                        'infrastructure, like"\n')
        self.assertVisual("today", 1, "'text' has 7 words, more than 6")

    def test_words_have_no_source(self):
        self.add_visual('kind = "words"\ntext = "deposits stop"\n'
                        'source = "lao-analysis"\n')
        self.assertVisual("today", 1, "may not have 'source'")

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

    def test_judgment_words_on_screen(self):
        self.add_visual(self.NUMBER.replace('"fund target"',
                                            '"a bold target"'))
        self.add_visual(self.TIMELINE.replace('"Ends"', '"Sweeping end"'),
                        after='for any program."\n'
                        'sources = ["lao-analysis"]')
        got = self.failures()
        self.assertEqual([(f.check, f.section, f.line, f.message)
                          for f in got],
                         [("judgment-word", "today", 1,
                           "judgment word 'bold' in visual label"),
                          ("judgment-word", "today", 3,
                           "judgment word 'Sweeping' in visual items")])

    def test_judgment_words_in_words_visual(self):
        self.edit("script.toml", "deposits stop, and",
                  "deposits stop, a bold move, and")
        self.add_visual('kind = "words"\ntext = "a bold move"\n',
                        after='a bold move, and that money goes to '
                        'infrastructure, like highways and housing, '
                        'instead."\nsources = ["lao-analysis"]')
        got = self.failures()
        self.assertEqual(sorted(f.message for f in got),
                         ["judgment word 'bold' in text",
                          "judgment word 'bold' in visual text"])

    def add_side_words(self, side, words):
        self.edit("script.toml", self.SIDE_LINE[side],
                  self.SIDE_LINE[side]
                  + f'\n\n[section.line.visual]\nkind = "words"\n'
                    f'text = "{words}"\n')

    def test_words_on_one_side(self):
        self.add_side_words("yes", "a larger reserve")
        [f] = self.assertOnly("side-visual", "yes", 0)
        self.assertIn("yes has words, no has none", f.message)

    def test_words_on_both_sides(self):
        self.add_side_words("yes", "a larger reserve")
        self.add_side_words("no", "the spending limit")
        self.assertEqual(self.failures(), [])

    def test_number_on_one_side(self):
        self.edit("script.toml", self.SIDE_LINE["no"],
                  self.SIDE_LINE["no"] + '\n\n[section.line.visual]\n'
                  'kind = "number"\ntext = "1978"\nlabel = "limit"\n'
                  'source = "arguments"\n')
        [f] = self.assertOnly("side-visual", "no", 0)
        self.assertIn("yes has none, no has number", f.message)

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
        [f] = self.assertOnly("side-parity")
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

    def test_airtime_imbalance(self):
        # Both sides have 79 words in 4 one-sentence lines: 32.35s each at
        # the stand-in narration's pace. Shrinking "no" by 10% makes it
        # 29.19s, past the 5% tolerance.
        write_narration(self.dir, stretch={"no": 0.9})
        [f] = self.assertOnly("airtime")
        self.assertRegex(f.message, r"yes=32\.\ds, no=29\.2s")

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
