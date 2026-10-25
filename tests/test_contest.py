import unittest

from ballotreels import ContestError, load_contest

from .helpers import PROP_2, ContestCopyTestCase


class LoadProp2Test(unittest.TestCase):
    def test_loads(self):
        c = load_contest(PROP_2)
        self.assertEqual(c.id, "ca-2026-11-03-prop-2")
        self.assertEqual(c.kind, "measure")
        self.assertEqual(c.script.contest, c.id)
        self.assertEqual(c.script.template, "measure")
        self.assertEqual(c.script.template_version, 2)
        self.assertEqual([s.id for s in c.script.sections],
                         ["what", "background", "background", "background",
                          "background", "today", "change", "fiscal", "yes",
                          "no", "vote"])
        self.assertEqual(c.source("lao-volatility").kind, "official-report")
        self.assertEqual(c.source("lao-analysis").kind,
                         "official-fiscal-analysis")
        self.assertIsNone(c.source("nope"))

    def test_line_fields(self):
        vote = load_contest(PROP_2).script.sections[-1]
        self.assertEqual(vote.lines[0].sources, ("quick-reference",))
        self.assertFalse(vote.lines[0].connective)
        self.assertIsNone(vote.lines[-1].sources)
        self.assertTrue(vote.lines[-1].connective)

    def test_section_labels(self):
        self.assertEqual(load_contest(PROP_2).script.labels(), (
            "what", "background[0]", "background[1]", "background[2]",
            "background[3]", "today", "change", "fiscal", "yes", "no",
            "vote"))

    def test_visual_fields(self):
        change = load_contest(PROP_2).script.sections[6]
        v = change.lines[0].visual
        self.assertEqual((v.kind, v.source, v.unit, v.labels, v.values,
                          v.figure),
                         ("bars", "lao-analysis", "%",
                          ["Today", "Proposition 2"], [10, 20], None))
        self.assertIsNone(change.lines[1].visual)

    def test_side_field(self):
        sides = {s.id: s.side for s in load_contest(PROP_2).script.sections}
        self.assertEqual(sides["yes"], "yes")
        self.assertEqual(sides["no"], "no")
        self.assertIsNone(sides["what"])


class LoadErrorTest(ContestCopyTestCase):
    def test_not_a_directory(self):
        with self.assertRaises(ContestError):
            load_contest(self.dir / "nope")

    def test_missing_script(self):
        (self.dir / "script.toml").unlink()
        with self.assertRaisesRegex(ContestError, "script.toml: not found"):
            load_contest(self.dir)

    def test_bad_toml(self):
        self.edit("script.toml", 'template = "measure"', 'template = ')
        with self.assertRaises(ContestError):
            load_contest(self.dir)

    def test_wrong_type(self):
        self.edit("script.toml", "template_version = 2",
                  'template_version = "2"')
        with self.assertRaisesRegex(ContestError, "template_version"):
            load_contest(self.dir)

    def test_bool_is_not_an_int(self):
        self.edit("script.toml", "standard_version = 2",
                  "standard_version = true")
        with self.assertRaisesRegex(ContestError, "standard_version"):
            load_contest(self.dir)

    def test_missing_line_text(self):
        self.edit("script.toml", 'text = "A no vote means',
                  'txt = "A no vote means')
        with self.assertRaisesRegex(ContestError, "section 'vote' line\\[1\\]"):
            load_contest(self.dir)

    def test_visual_must_be_a_table(self):
        self.edit("script.toml", '[section.line.visual]\nkind = "bars"',
                  'visual = "bars"\n[section.line.not_visual]\nkind = "bars"')
        with self.assertRaisesRegex(ContestError,
                                    "section 'change' line\\[0\\]: 'visual'"):
            load_contest(self.dir)

    def test_duplicate_source_id(self):
        self.edit("sources.toml", 'id = "text"', 'id = "arguments"')
        with self.assertRaisesRegex(ContestError, "duplicate source id"):
            load_contest(self.dir)


if __name__ == "__main__":
    unittest.main()
