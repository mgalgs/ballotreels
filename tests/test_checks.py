"""Each machine check, failing on a deliberately broken copy of Prop 2."""

import re
import unittest

from ballotreels import check_contest, load_contest, load_standard
from ballotreels.standard import (REPO_ROOT, SOURCE_KINDS,
                                  judgment_word_pattern, read_judgment_words)

from .helpers import PROP_2, ContestCopyTestCase


class Prop2PassesTest(unittest.TestCase):
    def test_no_failures(self):
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
        self.edit("script.toml", 'sources = ["guide-section"]\n\n[[section]]\n'
                  'id = "today"', 'sources = []\n\n[[section]]\nid = "today"')
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

    # 5. template
    def test_unknown_template(self):
        self.edit("script.toml", 'template = "measure"', 'template = "race"')
        self.assertOnly("template")

    def test_unknown_template_version(self):
        self.edit("script.toml", "template_version = 1",
                  "template_version = 2")
        self.assertOnly("template")

    def test_sections_out_of_order(self):
        self.edit("script.toml", 'id = "today"', 'id = "TMP"')
        self.edit("script.toml", 'id = "change"', 'id = "today"')
        self.edit("script.toml", 'id = "TMP"', 'id = "change"')
        [f] = self.assertOnly("template")
        self.assertIn("what, change, today", f.message)

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
        self.edit("script.toml", "The Legislature placed",
                  "The Legislature, in a FAIR process, placed")
        [f] = self.assertOnly("judgment-word", "what", 1)
        self.assertIn("'FAIR'", f.message)

    def test_judgment_word_in_heading(self):
        self.edit("script.toml", 'heading = "Fiscal effect"',
                  'heading = "Sweeping fiscal effect"')
        self.assertOnly("judgment-word", "fiscal")

    def test_judgment_multiword_and_hyphenated(self):
        self.edit("script.toml", "changes how much",
                  "is a common-sense change to how much")
        self.edit("script.toml", "The Legislature placed",
                  "In common\tsense terms, the Legislature placed")
        got = self.failures()
        self.assertEqual(
            sorted((f.section, f.line, f.message) for f in got),
            [("what", 0, "judgment word 'common-sense' in text"),
             ("what", 1, "judgment word 'common\\tsense' in text")])

    def test_judgment_word_not_inside_other_words(self):
        self.edit("script.toml", "The Legislature placed",
                  "The Legislature, a boldface affair, placed")
        self.assertEqual(self.failures(), [])

    # 8. standard version
    def test_standard_version(self):
        self.edit("script.toml", "standard_version = 1",
                  "standard_version = 0")
        self.assertOnly("standard-version")

    def test_reports_every_failure(self):
        self.edit("script.toml", 'contest = "ca-2026-11-03-prop-2"',
                  'contest = "x"')
        self.edit("script.toml", "standard_version = 1",
                  "standard_version = 0")
        self.edit("script.toml", "The Legislature placed",
                  "The bold Legislature placed")
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
