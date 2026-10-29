"""The checks that stand in, before narration, for what narrating would
otherwise reveal: spellings the transcript check mishears, sides whose
spoken lengths differ too much, and side lines with no verbatim basis in
their argument. They apply only to a script whose narration is missing or
stale."""

import io
import re
import shutil
import unittest
from dataclasses import replace

from ballotreels import check_contest, load_contest, load_standard
from ballotreels.cli import main
from ballotreels.checks import check_speakability, needs_narration
from ballotreels.standard import REPO_ROOT, Risk, read_speakability

from .helpers import PROP_2, ContestCopyTestCase, write_committed_narration

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
    """Each case edits one line of a copy whose narration is committed, so
    only that line (and the phrase after it) is fresh and linted, whatever
    else the real list would flag in the rest of the script."""

    def setUp(self):
        super().setUp()
        write_committed_narration(self.dir)

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

    def test_two_letter_acronym_plural_passes(self):
        # "IDs" is spelled out letter by letter and narrated fine.
        self.assertEqual(self.speak("Voters may show photo IDs."), [])

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
        # Only narration is spoken: a chart title may say "PACs". Every
        # line is linted here, so only the title's words are looked for.
        self.edit("script.toml",
                  'title = "Where General Fund money goes (approximate)"',
                  'title = "Where U.S. PACs money goes (approximate)"')
        got = check_speakability(load_contest(self.dir), STANDARD.speakability)
        self.assertEqual([str(f) for f in got
                          if "U.S." in f.message or "PACs" in f.message], [])


class CheckCommandFreshnessTest(ContestCopyTestCase):
    """`python -m ballotreels check` judges a line fresh against the
    contest's committed narration: a phrase it would reuse is not linted,
    even where the real list matches it (Prop 2's "From 1980 to 2014"), and
    an edited line is."""

    YEARS = "'1980 to 2014'"

    def setUp(self):
        super().setUp()
        write_committed_narration(self.dir)

    def check(self):
        out = io.StringIO()
        code = main(["check", str(self.dir)], out=out)
        return code, out.getvalue()

    def test_current_narration_passes(self):
        self.assertTrue(any(self.YEARS in f.message for f in
                            check_speakability(load_contest(self.dir),
                                               STANDARD.speakability)))
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("PASS "), out)

    def test_fresh_line_is_linted(self):
        self.edit("script.toml", NO_LINE,
                  'text = "A no vote means the rules stay, unless a driver '
                  'consents."')
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("[speakability] vote.line[1]: 'consents'", out)
        self.assertNotIn(self.YEARS, out)


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


PROP_141 = REPO_ROOT / "data" / "az-2026-11-03" / "prop-141"
# a copy's narration is its recorded take, whether or not a checkout has
# the take's audio (narration_store)
WITHOUT_AUDIO = shutil.ignore_patterns("narration.wav")


class ReusedPhraseTest(unittest.TestCase):
    """A stale narration is re-narrated phrase by phrase: `say` reuses every
    phrase whose text and preceding phrase are unchanged, so only the
    phrases it would synthesise afresh are linted. Prop 141's vote line
    says "without consent" and passed the real transcript check."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "prop-141"
        shutil.copytree(PROP_141, self.dir, ignore=WITHOUT_AUDIO)

    def failures(self, old, new):
        script = self.dir / "script.toml"
        text = script.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1)
        script.write_text(text.replace(old, new), encoding="utf-8")
        c = load_contest(self.dir)
        self.assertTrue(needs_narration(c))
        return only(check_contest(c, STANDARD), "speakability")

    def test_edit_elsewhere_does_not_lint_reused_line(self):
        self.assertEqual(self.failures(
            "how many miles people drive.",
            "how many miles people drive each year."), [])

    def test_edit_before_relints_the_next_phrase(self):
        # The vote line's first phrase quotes the edited line as context,
        # so `say` speaks it again: it is linted.
        got = self.failures("road funding option prematurely.",
                            "road funding option too soon.")
        self.assertEqual([(f.section, f.line) for f in got], [("vote", 0)])
        self.assertIn("'consent'", got[0].message)


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
                ("nearly $90,000.", "nearly ninety thousand dollars."),
                ("over $2 million on", "over two million dollars on"),
                ("$1.4 billion", "one point four billion dollars"),
                ("20%", "twenty percent"), ("10 percent", "ten percent"),
                ("in 1978,", "in nineteen seventy-eight,"),
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

    def test_edit_outside_the_sides_is_not_estimated(self):
        # Re-narrating after a background edit re-speaks that line and the
        # one after it, not a side: the sides keep the takes that passed
        # the real airtime check (1.7 s apart, where the estimate says
        # 1.1 s), so they are not estimated again.
        shutil.rmtree(self.dir)
        shutil.copytree(CI_132, self.dir, ignore=WITHOUT_AUDIO)
        path = self.dir / "script.toml"
        old = path.read_text(encoding="utf-8")
        self.assertIn("proposed by initiative petition", old)
        path.write_text(old.replace("proposed by initiative petition",
                                    "proposed by an initiative petition"),
                        encoding="utf-8")
        self.assertTrue(needs_narration(load_contest(self.dir)))
        self.assertEqual(self.parity(), [])

    def test_edit_to_a_side_is_estimated(self):
        # With CI-132's narration committed, writing the opponents' draft
        # back in re-speaks that side, so both are estimated, and fail.
        shutil.rmtree(self.dir)
        shutil.copytree(CI_132, self.dir, ignore=WITHOUT_AUDIO)
        self.set_no(CI_132_NO_DRAFT)
        [f] = self.parity()
        self.assertIn("shorten yes", f.message)
        self.assertIn("nearly ninety thousand dollars.'", f.message)

    def test_committed_narration_is_not_estimated(self):
        # Narrated and committed, CI-132 passed the real airtime check
        # (1.7 s): the estimate does not second-guess it.
        c = load_contest(CI_132)
        self.assertFalse(needs_narration(c))
        self.assertEqual(only(check_contest(c, STANDARD), "spoken-parity"),
                         [])


I_194 = REPO_ROOT / "data" / "mt-2026-11-03" / "i-194"
# The supporters' line as first written: it reads as a complaint, where
# the argument's point is that Montana may therefore limit them.
I_194_YES_DRAFT = ("Supporters say Montana grants artificial persons every "
                   "power, and can end anonymous dark money in elections.")


class SideBasisTest(ContestCopyTestCase):
    """Prop 2's copy has no narration, so its side lines need a basis."""

    def basis(self):
        return only(check_contest(load_contest(self.dir), STANDARD),
                    "side-basis")

    def test_fixture_bases_pass(self):
        # Including ones typed with straight quotes where the guide prints
        # curly ones ("rebate", doesn't, state's).
        self.assertEqual(self.basis(), [])

    def test_missing_basis_fails_before_narration(self):
        self.edit("script.toml", 'basis = ["Currently, it doesn\'t dedicate '
                  'any new dollars to any of those priorities.", "It needs '
                  'the discipline to follow the rules already in place"]\n',
                  "")
        [f] = self.basis()
        self.assertEqual((f.section, f.line), ("no", 1))
        self.assertIn("has no 'basis'", f.message)

    def test_basis_not_in_the_argument(self):
        self.edit("script.toml", "the rules already in place",
                  "the rules already on the books")
        [f] = self.basis()
        self.assertEqual((f.section, f.line), ("no", 1))
        self.assertIn("does not appear verbatim", f.message)
        self.assertIn("'arguments'", f.message)

    def test_basis_too_short(self):
        self.edit("script.toml", '"It needs the discipline to follow the '
                  'rules already in place"', '"follow the rules"')
        [f] = self.basis()
        self.assertIn("under 6 words", f.message)

    def test_basis_must_cite_an_argument(self):
        self.edit("script.toml", 'sources = ["arguments"]\nbasis = ["David',
                  'sources = ["lao-analysis"]\nbasis = ["David')
        got = self.basis()
        self.assertTrue(any("cites no 'official-argument'" in f.message
                            for f in got), [str(f) for f in got])

    def test_only_side_lines_have_a_basis(self):
        self.edit("script.toml",
                  'text = "A no vote means the current rules would not '
                  'change."\n',
                  'text = "A no vote means the current rules would not '
                  'change."\nbasis = ["It needs the discipline to follow '
                  'the rules already in place"]\n')
        [f] = self.basis()
        self.assertEqual(f.section, "vote")
        self.assertIn("only a side's lines", f.message)

    def test_unfiled_side_needs_none(self):
        self.edit("script.toml", 'side = "no"\n', 'side = "no"\nfiled = false\n')
        path = self.dir / "script.toml"
        text = path.read_text(encoding="utf-8")
        no = text.index('side = "no"')
        end = text.index('id = "vote"')
        path.write_text(text[:no] + re.sub(r"basis = \[.*\]\n", "",
                                            text[no:end]) + text[end:],
                        encoding="utf-8")
        self.assertEqual(self.basis(), [])


class SideBasisGateTest(unittest.TestCase):
    def test_narrated_scripts_need_no_basis(self):
        # Every committed contest is narrated; none has a basis yet, and
        # none fails for it.
        import glob
        for path in sorted(glob.glob(str(REPO_ROOT / "data" / "*" / "*" /
                                          "script.toml"))):
            c = load_contest(path.rsplit("/", 1)[0])
            if needs_narration(c):
                continue
            from ballotreels.checks import check_side_basis
            self.assertEqual(check_side_basis(c, required=False), [], c.id)


@unittest.skipIf(shutil.which("pdftotext") is None, "needs pdftotext")
class I194BasisTest(unittest.TestCase):
    """Montana I-194, whose argument is a PDF (ligatures, words joined or
    split across lines), copied without its narration."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "i-194"
        shutil.copytree(I_194, self.dir,
                        ignore=shutil.ignore_patterns("narration.*"))

    def set_yes(self, text, basis=None):
        path = self.dir / "script.toml"
        old = path.read_text(encoding="utf-8")
        start = old.index('text = "Supporters say')
        end = old.index("\n", old.index("sources =", start))
        import json
        new = f'text = "{text}"\nsources = ["arguments"]'
        if basis is not None:
            new += "\nbasis = [" + ", ".join(json.dumps(b) for b in basis) + "]"
        path.write_text(old[:start] + new + old[end:], encoding="utf-8")

    def basis(self):
        return [f for f in only(check_contest(load_contest(self.dir),
                                              STANDARD), "side-basis")
                if f.section == "yes"]

    def test_draft_without_basis_is_caught(self):
        self.set_yes(I_194_YES_DRAFT)
        [f] = self.basis()
        self.assertIn("has no 'basis'", f.message)

    def test_draft_with_its_basis_passes_the_machine_check(self):
        # The check makes the line traceable; whether the line says what
        # its basis says is the reviewer's (SCRIPT-RECIPE.md, "Sides").
        self.set_yes("Supporters say Montana grants artificial persons all "
                     "the powers they have, so it can end dark money in "
                     "elections.",
                     ["Montana grants them every power they have.",
                      "And Montana has reserved the authority to modify "
                      "those"])
        self.assertEqual(self.basis(), [])

    def test_pdf_ligatures_and_line_breaks(self):
        self.set_yes(I_194_YES_DRAFT,
                     ["artificial persons are creations of statute that "
                      "exist only by virtue of powers affirmatively",
                      "TV ads, and digital and social-media advertising"])
        self.assertEqual(self.basis(), [])

    def test_paraphrase_is_not_a_basis(self):
        self.set_yes(I_194_YES_DRAFT,
                     ["Montana grants artificial persons every power they "
                      "have."])
        [f] = self.basis()
        self.assertIn("does not appear verbatim", f.message)
