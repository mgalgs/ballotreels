"""The questions a video raises (STANDARD.md section 10): another
government's record (`precedent-record`) only in the background, and a
`[[question]]` record whose every question is answered by lines that
exist or marked as answered by no official source."""

import unittest

from ballotreels import check_contest, load_contest
from ballotreels.checks import check_questions

from .helpers import ContestCopyTestCase, unlinted_standard

ELSEWHERE = ('\n[[source]]\nid = "elsewhere"\nkind = "precedent-record"\n'
             'publisher = "Another state\'s legislature"\n'
             'url = "https://example.gov/law"\n'
             'file = "sources/analysis.html"\nretrieved = "2026-10-28"\n')
BACKGROUND_LINE = ('text = "Each year, the state spends about 250 billion '
                   'dollars from its General Fund, the account that pays for '
                   'most public services."\nsources = ["lao-analysis"]')
TODAY_LINE = ('text = "Today, the state has about 20 billion dollars '
              'in reserves it can use for any program."\n'
              'sources = ["lao-analysis"]')


class QuestionsTest(ContestCopyTestCase):
    def setUp(self):
        super().setUp()
        path = self.dir / "sources.toml"
        path.write_text(path.read_text(encoding="utf-8") + ELSEWHERE,
                        encoding="utf-8")

    def failures(self):
        return check_questions(load_contest(self.dir))

    def ask(self, *tables):
        """Give the background line id "spending" and append `tables`."""
        text = BACKGROUND_LINE.split("\n")[0]
        self.edit("script.toml", text, text + '\nid = "spending"')
        path = self.dir / "script.toml"
        path.write_text(path.read_text(encoding="utf-8") + "".join(
            f"\n[[question]]\n{t}\n" for t in tables), encoding="utf-8")

    def test_a_record_answered_and_unanswered_passes(self):
        self.edit("script.toml", BACKGROUND_LINE, BACKGROUND_LINE.replace(
            '["lao-analysis"]', '["lao-analysis", "elsewhere"]'))
        self.ask('ask = "How big is the budget?"\nlines = ["spending"]',
                 'ask = "Who keeps the money?"\nunanswered = true')
        self.assertEqual(self.failures(), [])
        self.assertEqual(
            check_contest(load_contest(self.dir), unlinted_standard()), [])

    def test_no_record_passes(self):
        self.assertEqual(self.failures(), [])  # optional under version 2

    def test_precedent_outside_background_fails(self):
        self.edit("script.toml", TODAY_LINE, TODAY_LINE.replace(
            '["lao-analysis"]', '["lao-analysis", "elsewhere"]'))
        [f] = self.failures()
        self.assertEqual((f.check, f.section, f.line), ("precedent", "today", 3))
        self.assertIn("'elsewhere'", f.message)

    def test_precedent_chart_outside_background_fails(self):
        self.edit("script.toml", 'General Fund taxes"\nsource = "lao-analysis"',
                  'General Fund taxes"\nsource = "elsewhere"')
        [f] = self.failures()
        self.assertEqual((f.check, f.section), ("precedent", "change"))
        self.assertIn("has a chart citing", f.message)

    def test_missing_line_fails(self):
        self.ask('ask = "How big is the budget?"\nlines = ["spend"]')
        [f] = self.failures()
        self.assertEqual(f.check, "questions")
        self.assertIn("'spend'", f.message)

    def test_neither_answered_nor_unanswered_fails(self):
        self.ask('ask = "Who keeps the money?"')
        [f] = self.failures()
        self.assertIn("neither answered nor marked unanswered", f.message)

    def test_an_empty_list_is_no_answer(self):
        self.ask('ask = "Who keeps the money?"\nlines = []')
        [f] = self.failures()
        self.assertIn("neither", f.message)

    def test_both_answered_and_unanswered_fails(self):
        self.ask('ask = "How big is the budget?"\nlines = ["spending"]\n'
                 'unanswered = true')
        [f] = self.failures()
        self.assertIn("one or the other", f.message)

    def test_unanswered_false_fails(self):
        self.ask('ask = "How big is the budget?"\nlines = ["spending"]\n'
                 'unanswered = false')
        [f] = self.failures()
        self.assertIn("may only be true", f.message)

    def test_question_needs_words(self):
        self.ask('lines = ["spending"]')
        [f] = self.failures()
        self.assertIn("needs 'ask'", f.message)

    def test_duplicate_line_id_fails(self):
        self.ask('ask = "How big is the budget?"\nlines = ["spending"]')
        self.edit("script.toml", TODAY_LINE, TODAY_LINE + '\nid = "spending"')
        [f] = self.failures()
        self.assertIn("used by 2 lines", f.message)


if __name__ == "__main__":
    unittest.main()
