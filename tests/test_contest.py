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
        self.assertEqual(c.script.template_version, 1)
        self.assertEqual([s.id for s in c.script.sections],
                         ["what", "today", "change", "fiscal", "yes", "no",
                          "vote"])
        self.assertEqual(c.source("lao-analysis").kind,
                         "official-fiscal-analysis")
        self.assertIsNone(c.source("nope"))

    def test_line_fields(self):
        vote = load_contest(PROP_2).script.sections[-1]
        self.assertEqual(vote.lines[0].sources, ("quick-reference",))
        self.assertFalse(vote.lines[0].connective)
        self.assertIsNone(vote.lines[-1].sources)
        self.assertTrue(vote.lines[-1].connective)

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
        self.edit("script.toml", "template_version = 1",
                  'template_version = "1"')
        with self.assertRaisesRegex(ContestError, "template_version"):
            load_contest(self.dir)

    def test_bool_is_not_an_int(self):
        self.edit("script.toml", "standard_version = 1",
                  "standard_version = true")
        with self.assertRaisesRegex(ContestError, "standard_version"):
            load_contest(self.dir)

    def test_missing_line_text(self):
        self.edit("script.toml", 'text = "A no vote means',
                  'txt = "A no vote means')
        with self.assertRaisesRegex(ContestError, "section 'vote' line\\[1\\]"):
            load_contest(self.dir)

    def test_duplicate_source_id(self):
        self.edit("sources.toml", 'id = "text"', 'id = "arguments"')
        with self.assertRaisesRegex(ContestError, "duplicate source id"):
            load_contest(self.dir)


if __name__ == "__main__":
    unittest.main()
