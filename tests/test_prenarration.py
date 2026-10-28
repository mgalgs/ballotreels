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


CI_132 = REPO_ROOT / "data" / "mt-2026-11-03" / "ci-132"
CI_132_YES = ("Supporters say judges should be elected on their record and "
              "qualifications, not politics, and a recent law lets political "
              "parties give judicial candidates nearly $90,000.")
# The opponents' line as first written: 25 words each side, but narrated
# 2.1 s shorter than the supporters', past the 2 s the airtime check pads.
CI_132_NO_DRAFT = ("Opponents say voters are entitled to know the party "
                   "preferences of judicial candidates, and out-of-state "
                   "special interests have spent over $2 million on the "
                   "amendment.")


class SpokenTextTest(unittest.TestCase):
    def test_numbers_said_in_full(self):
        from ballotreels.spoken import spoken_text
        for written, said in [
                ("nearly $90,000.", "nearly ninety thousand dollars ."),
                ("over $2 million on", "over two million dollars on"),
                ("$1.4 billion", "one point four billion dollars"),
                ("20%", "twenty percent"), ("10 percent", "ten percent"),
                ("in 1978,", "in nineteen seventy-eight ,"),
                ("by 2026", "by twenty twenty-six"),
                ("in 2005", "in two thousand five"),
                ("about 1,500 clinics", "about one thousand five hundred "
                 "clinics"),
                ("DEI & ID", "D E I and I D")]:
            self.assertEqual(spoken_text(written), said, written)

    def test_syllables(self):
        from ballotreels.spoken import word_syllables
        for word, n in [("judges", 2), ("qualifications", 5), ("the", 1),
                        ("make", 1), ("little", 2), ("voted", 2),
                        ("passed", 1), ("w", 3)]:
            self.assertEqual(word_syllables(word), n, word)

    def test_fit_to_committed_narrations(self):
        # The coefficients were fitted to every committed narration's
        # per-phrase timings; they should still describe them.
        import glob
        import json
        from ballotreels.spoken import phrase_seconds
        errs = []
        for path in glob.glob(str(REPO_ROOT / "data" / "*" / "*" /
                                  "narration.json")):
            doc = json.loads(open(path, encoding="utf-8").read())
            if doc.get("inputs", {}).get("engine") != "gemini":
                continue
            errs += [phrase_seconds(p["text"]) - (p["end"] - p["start"])
                     for p in doc["phrases"]]
        self.assertGreater(len(errs), 100)
        rms = (sum(e * e for e in errs) / len(errs)) ** 0.5
        self.assertLess(rms, 0.55)
        self.assertLess(abs(sum(errs) / len(errs)), 0.1)


class SpokenParityTest(unittest.TestCase):
    """Montana CI-132's sides, copied without their narration."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "ci-132"
        shutil.copytree(CI_132, self.dir,
                        ignore=shutil.ignore_patterns("narration.*"))

    def set_no(self, text):
        path = self.dir / "script.toml"
        old = path.read_text(encoding="utf-8")
        start = old.index('text = "Opponents say')
        end = old.index("\n", start)
        path.write_text(old[:start] + f'text = "{text}"' + old[end:],
                        encoding="utf-8")

    def parity(self):
        return only(check_contest(load_contest(self.dir), STANDARD),
                    "spoken-parity")

    def test_ci_132_draft_is_caught(self):
        self.set_no(CI_132_NO_DRAFT)
        c = load_contest(self.dir)
        yes = [ln.text for s in c.script.sections if s.side == "yes"
               for ln in s.lines]
        self.assertEqual(yes, [CI_132_YES])
        [f] = self.parity()
        self.assertIn("ninety thousand dollars", f.message)
        self.assertIn("shorten yes", f.message)

    def test_balanced_sides_pass(self):
        self.set_no("Opponents say voters are entitled to know the party "
                    "preferences of judicial candidates, and out-of-state "
                    "special interests have already spent more than two "
                    "million dollars on the amendment.")
        self.assertEqual(self.parity(), [])

    def test_unfiled_side_is_exempt(self):
        self.set_no("Opponents say no.")
        self.assertTrue(self.parity())
        path = self.dir / "script.toml"
        path.write_text(path.read_text(encoding="utf-8").replace(
            'side = "no"\n', 'side = "no"\nfiled = false\n'),
            encoding="utf-8")
        self.assertEqual(self.parity(), [])

    def test_committed_narration_is_not_estimated(self):
        # Narrated and committed, CI-132 passed the real airtime check
        # (1.7 s): the estimate does not second-guess it.
        c = load_contest(CI_132)
        self.assertFalse(needs_narration(c))
        self.assertEqual(only(check_contest(c, STANDARD), "spoken-parity"),
                         [])
