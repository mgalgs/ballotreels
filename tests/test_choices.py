"""Choice questions: a script's [choices] table, its checks, and the grid
pages its options are drawn on (docs/SCRIPT-FORMAT.md, STANDARD.md
section 8)."""

import tempfile
import unittest
from pathlib import Path

from ballotreels import check_contest, grid, load_contest
from ballotreels.checks import spoken_forms
from ballotreels.narration import section_order

from .choice_fixture import label, spoken, write_choice_contest
from .helpers import ContestCopyTestCase


class GridTest(unittest.TestCase):
    def test_smallest_grid_that_fits(self):
        self.assertEqual(grid.grid_for(2), (1, 2))
        self.assertEqual(grid.grid_for(3), (1, 3))
        self.assertEqual(grid.grid_for(4), (2, 2))
        self.assertEqual(grid.grid_for(5), (2, 3))
        self.assertEqual(grid.grid_for(6), (2, 3))
        with self.assertRaises(ValueError):
            grid.grid_for(7)

    def test_page_split(self):
        for n, sizes in ((2, (2,)), (3, (3,)), (4, (4,)), (5, (5,)),
                         (6, (6,)), (7, (4, 3)), (8, (4, 4)),
                         (12, (6, 6)), (13, (5, 4, 4))):
            with self.subTest(n=n):
                self.assertEqual(grid.page_sizes(n), sizes)
                pages = grid.pages(n)
                self.assertEqual([len(p) for p in pages], list(sizes))
                # every option once, in ballot order
                self.assertEqual([k for p in pages for k in p], list(range(n)))

    def test_each_page_its_own_smallest_grid(self):
        self.assertEqual([grid.grid_for(len(p)) for p in grid.pages(7)],
                         [(2, 2), (1, 3)])
        self.assertEqual([grid.grid_for(len(p)) for p in grid.pages(13)],
                         [(2, 3), (2, 2), (2, 2)])

    def test_cells_in_reading_order(self):
        self.assertEqual(grid.cells(2), ((0, 0), (0, 1)))
        self.assertEqual(grid.cells(3), ((0, 0), (0, 1), (0, 2)))
        self.assertEqual(grid.cells(4), ((0, 0), (1, 0), (0, 1), (1, 1)))
        # five in 2x3: the last cell (1, 2) stays empty
        self.assertEqual(grid.cells(5),
                         ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2)))


class SpokenFormsTest(unittest.TestCase):
    def test_parenthesised_parts_may_be_left_out(self):
        # compared as the card is: no space before punctuation
        forms = spoken_forms("Colt M1911 .45 automatic Colt pistol (.45 ACP)")
        self.assertEqual(forms, {"Colt M1911.45 automatic Colt pistol (.45 ACP)",
                                 "Colt M1911.45 automatic Colt pistol"})
        self.assertIn("Winchester Model 1873 “Gun that Won the West”",
                      spoken_forms("Winchester Model 1873 “Gun that Won the "
                                   "West” (.44-40)"))


class ChoiceTestCase(unittest.TestCase):
    N = 6

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = write_choice_contest(Path(tmp.name) / "c", self.N)

    def edit(self, old, new, count=1):
        path = self.dir / "script.toml"
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), count, old)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def failures(self):
        return [str(f) for f in check_contest(load_contest(self.dir))]

    def assertFails(self, needle):
        got = self.failures()
        self.assertTrue(any(needle in f for f in got), got)


class ChoiceCheckTest(ChoiceTestCase):
    def test_passes(self):
        self.assertEqual(self.failures(), [])
        c = load_contest(self.dir)
        self.assertEqual(len(c.script.choices.choices), 6)
        self.assertEqual(c.script.choices.choices[0].printed,
                         "(a) Model A tree (No. 1)")
        self.assertEqual(section_order(c),
                         ("what", "choices", "fiscal", "vote"))

    def test_no_sides(self):
        self.edit('id = "fiscal"\n', 'id = "fiscal"\nside = "yes"\n')
        self.assertFails("has side = 'yes' but is not a side section")

    def test_yes_no_sections_do_not_fit(self):
        self.edit('id = "choices"', 'id = "change"')
        self.assertFails("a choice question under measure v2 requires what, "
                         "background*, choices, fiscal, vote")

    def test_card_has_no_yes_or_no(self):
        self.edit('summary = ', 'yes = "A YES vote"\nno = "A NO vote"\n'
                                'summary = ')
        self.assertFails("the card has 'yes'/'no' lines")

    def test_label_verbatim(self):
        self.edit('label = "Model C tree (No. 3)"',
                  'label = "Model C tree (No. 33)"')
        self.assertFails("choice '(c) Model C tree (No. 33)' does not "
                         "appear verbatim in source 'ballot'")

    def test_letter_paired_with_its_label(self):
        self.edit('letter = "(c)"', 'letter = "(d)"')
        self.edit('letter = "(d)"\nlabel = "Model D', 'letter = "(c)"\n'
                  'label = "Model D')
        self.assertFails("does not appear verbatim")

    def test_letters_in_ballot_order(self):
        self.edit('letter = "(b)"', 'letter = "(z)"')
        self.assertFails("are not in ballot order")

    def test_letters_all_or_none(self):
        self.edit('letter = "(b)"\n', '')
        self.assertFails("some choices have a 'letter'")

    def test_spoken_is_the_label(self):
        self.edit('spoken = "Model B tree"', 'spoken = "the B tree"')
        self.assertFails("spoken 'the B tree' is not the label as printed")

    def test_illustration_must_exist(self):
        self.edit('illustration = "state-capitol"\n\n[[choices.choice]]\n'
                  'letter = "(b)"',
                  'illustration = "no-such-drawing"\n\n[[choices.choice]]\n'
                  'letter = "(b)"')
        self.assertFails("names 'no-such-drawing', which is not in")

    def test_source_is_the_cards(self):
        self.edit('[choices]\nsource = "ballot"', '[choices]\nsource = "note"')
        self.assertFails("is not the card's 'ballot'")

    def test_at_least_two(self):
        text = (self.dir / "script.toml").read_text()
        a = text.index("[[choices.choice]]")
        b = text.index("[[section]]")
        (self.dir / "script.toml").write_text(text[:a] + text[b:])
        self.assertFails("has 0 choices")

    def test_every_choice_named(self):
        self.edit(f"{spoken(3)}, ", "")
        self.assertFails(f"choice '{spoken(3)}' is named 0 times")

    def test_ballot_order(self):
        self.edit(f"{spoken(1)}, {spoken(2)}", f"{spoken(2)}, {spoken(1)}")
        self.assertFails("out of ballot order")

    def test_named_equally_often(self):
        self.edit('text = "Voters choose only one answer."',
                  f'text = "Voters choose only one answer, such as {spoken(0)}."')
        self.assertFails("names the choices unequally often")

    def test_named_the_same_elsewhere_is_fine(self):
        names = ", ".join(spoken(k) for k in range(6))
        self.edit('text = "Voters choose only one answer."',
                  f'text = "Voters choose one of {names}."')
        self.assertEqual(self.failures(), [])

    def test_choices_visual_only_in_its_section(self):
        self.edit('kind = "page"\nsource = "ballot"\nhighlight = ["Please',
                  'kind = "choices"\nsource = "ballot"\n#highlight = ["Please')
        self.assertFails("a 'choices' visual belongs only in the 'choices' "
                         "section")

    def test_no_other_visual_on_the_grid(self):
        self.edit('kind = "choices"\nsource = "ballot"',
                  'kind = "illustration"\nname = "state-capitol"')
        self.assertFails("this line has a 'illustration' visual")

    def test_choices_visual_needs_a_choices_table(self):
        c = ContestCopyTestCase("run")
        c.setUp()
        try:
            c.edit("script.toml",
                   'kind = "bars"\ntitle = "Rainy Day Fund target, as a share '
                   'of General Fund taxes"', 'kind = "choices"\n#')
            got = [str(f) for f in check_contest(load_contest(c.dir))]
            self.assertTrue(any("needs a [choices] table" in f for f in got),
                            got)
        finally:
            c.doCleanups()

    def test_label_exempt_from_judgment_words_but_narration_is_not(self):
        self.edit(f'label = "{label(0)}"', 'label = "Model A fair tree"')
        self.assertFails("does not appear verbatim")
        self.assertFalse(any("judgment" in f for f in self.failures()))


class PagedChoiceTest(ChoiceTestCase):
    N = 7  # two pages: 4 + 3

    def test_passes(self):
        self.assertEqual(self.failures(), [])

    def test_one_visual_per_page(self):
        self.edit('\n[section.line.visual]\nkind = "choices"\n'
                  'source = "ballot"\n\n[[section]]\nid = "fiscal"',
                  '\n[[section]]\nid = "fiscal"')
        self.assertFails("has 1 'choices' visual; 7 choices take 2 grid "
                         "pages (4 + 3), one visual each")

    def test_named_on_its_own_page(self):
        # move option e from page 2's line to page 1's
        self.edit(f"{spoken(3)}.", f"{spoken(3)}, {spoken(4)}.")
        self.edit(f"lists {spoken(4)}, ", "lists ")
        self.assertFails(f"choice '{spoken(4)}' is named while grid page 1 "
                         f"is up, which does not show it")


if __name__ == "__main__":
    unittest.main()
