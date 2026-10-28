"""The checks that stand in, before narration, for what narrating would
otherwise reveal: spellings the transcript check mishears, sides whose
spoken lengths differ too much, and side lines with no verbatim basis in
their argument. They apply only to a script whose narration is missing or
stale."""

import shutil
import unittest
from dataclasses import replace

from ballotreels import check_contest, load_contest, load_standard
from ballotreels.checks import check_speakability, needs_narration
from ballotreels.standard import REPO_ROOT, Risk, read_speakability

from .helpers import PROP_2, ContestCopyTestCase

import re

NO_LINE = ('text = "A no vote means the current rules would not change."')
STANDARD = load_standard()


def only(failures, check):
    return [f for f in failures if f.check == check]


class SpeakabilityListTest(unittest.TestCase):
    def test_list_loads(self):
        risks = read_speakability(REPO_ROOT / "standard" / "speakability.txt")
        self.assertGreaterEqual(len(risks), 5)
        for r in risks:
            self.assertTrue(r.reason and r.suggestion)

    def test_bad_entry_names_its_line(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "list.txt"
            path.write_text("# comment\n\nfoo | no suggestion\n",
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"list\.txt:3"):
                read_speakability(path)


class SpeakabilityTest(ContestCopyTestCase):
    def speak(self, text):
        self.edit("script.toml", NO_LINE, f'text = "{text}"')
        return only(check_contest(load_contest(self.dir), STANDARD),
                    "speakability")

    def assertFlags(self, text, token):
        got = self.speak(text)
        self.assertEqual(len(got), 1, [str(f) for f in got])
        f = got[0]
        self.assertEqual((f.section, f.line), ("vote", 1))
        self.assertIn(repr(token), f.message)
        self.assertIn("instead", f.message)
        return f

    # The four real cases the transcript check failed on.
    def test_consents(self):
        # Arizona Proposition 141, heard as "can sense".
        f = self.assertFlags("Governments also could not monitor or limit "
                             "miles driven, unless a driver consents.",
                             "consents")
        self.assertIn("can sense", f.message)
        self.assertIn("agrees", f.message)

    def test_pacs(self):
        # Montana I-194, heard as "packs" and "pacts".
        self.assertFlags("Opponents say the initiative restricts free speech "
                         "of businesses, churches and community groups, "
                         "sparing out-of-state PACs.", "PACs")

    def test_us(self):
        self.assertFlags("The amendment would require an Ohio driver license "
                         "or state ID, a U.S. passport, or a military ID.",
                         "U.S.")

    def test_property_s(self):
        self.assertFlags("Other property's cap on yearly assessment "
                         "increases would fall from 10 to 5 percent.",
                         "property's")

    def test_any_acronym_plural(self):
        self.assertFlags("Committees called SuperPACs and LLCs spend.",
                         "LLCs")

    def test_eg(self):
        self.assertFlags("Some funds, e.g. reserves, are kept.", "e.g.")

    def test_clean_wording_passes(self):
        self.assertEqual(self.speak(
            "Opponents say it spares out-of-state political committees, "
            "unless a driver agrees, and the state's United States "
            "passport rule and the value of the property stay."), [])

    def test_states_possessive_passes(self):
        # "state's" and "states" compare equal in the transcript check.
        self.assertEqual(self.speak("Today's rules and the state's fund."),
                         [])

    def test_on_screen_text_not_checked(self):
        # Only narration is spoken: a chart title may say "PACs".
        self.edit("script.toml",
                  'title = "Where General Fund money goes (approximate)"',
                  'title = "Where U.S. PACs money goes (approximate)"')
        self.assertEqual(only(check_contest(load_contest(self.dir), STANDARD),
                              "speakability"), [])


class GateTest(unittest.TestCase):
    """A narration that matches the script already passed the real
    transcript check: the speakability list is not applied to it."""

    def setUp(self):
        self.risky = replace(STANDARD, speakability=(
            Risk(re.compile(r"Rainy Day"), "test reason", "test suggestion"),))

    def test_current_narration_is_not_linted(self):
        c = load_contest(PROP_2)
        self.assertFalse(needs_narration(c))
        self.assertEqual(only(check_contest(c, self.risky), "speakability"),
                         [])
        self.assertTrue(check_speakability(c, self.risky.speakability))

    def test_missing_narration_is_linted(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "prop-2"
            shutil.copytree(PROP_2, dest, ignore=shutil.ignore_patterns(
                "narration.*"))
            c = load_contest(dest)
            self.assertTrue(needs_narration(c))
            self.assertTrue(only(check_contest(c, self.risky),
                                 "speakability"))

    def test_stale_narration_is_linted(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "prop-2"
            shutil.copytree(PROP_2, dest)
            script = dest / "script.toml"
            script.write_text(script.read_text(encoding="utf-8").replace(
                "would not change.", "would stay the same."),
                encoding="utf-8")
            c = load_contest(dest)
            self.assertTrue(needs_narration(c))
            self.assertTrue(only(check_contest(c, self.risky),
                                 "speakability"))
