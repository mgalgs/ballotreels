import io
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from ballotreels.cli import main
from ballotreels.contest import load_contest
from ballotreels.narration import narration_text

from .helpers import PROP_2, REPO, ContestCopyTestCase, unlinted_standard
from .test_crash_course import UT


class CliTest(ContestCopyTestCase):
    def run_cli_cmd(self, command, *dirs):
        out = io.StringIO()
        # The copy has no narration, so every line would be linted.
        with mock.patch("ballotreels.cli.load_standard", unlinted_standard):
            code = main([command, *map(str, dirs)], out=out)
        return code, out.getvalue().splitlines()

    def run_cli(self, *dirs):
        return self.run_cli_cmd("check", *dirs)

    WORDS = ("words what=41 background[0]=70 background[1]=74 "
             "background[2]=52 background[3]=27 today=81 change=97 fiscal=49 "
             "yes=79 no=79 vote=43; no plays first")

    def test_prop_2_script_passes(self):
        # The copy has no narration sidecars, so airtime isn't measured.
        code, lines = self.run_cli(self.dir)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [f"PASS ca-2026-11-03-prop-2; {self.WORDS}"])

    def test_prop_2_with_its_narration(self):
        # Its sides' spoken durations differ by 1.4s, within the pad cap,
        # so check_airtime's padded layout covers it: a clean PASS.
        code, lines = self.run_cli(PROP_2)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [f"PASS ca-2026-11-03-prop-2; {self.WORDS}"])

    def test_failures_one_per_line(self):
        clean = self.dir.parent / "clean"  # an unbroken copy, to pass
        shutil.copytree(self.dir, clean)
        self.edit("script.toml", "standard_version = 2",
                  "standard_version = 0")
        self.edit("script.toml", "The Legislature put it",
                  "The bold Legislature put it")
        code, lines = self.run_cli(clean, self.dir)
        self.assertEqual(code, 1)
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("PASS"))
        self.assertIn("[judgment-word] what.line[1]: judgment word 'bold'",
                      lines[1])
        self.assertIn("[standard-version]", lines[2])
        self.assertTrue(lines[3].startswith(
            "FAIL ca-2026-11-03-prop-2: 2 failures; words "))

    def test_unloadable_contest(self):
        (self.dir / "script.toml").unlink()
        code, lines = self.run_cli(self.dir)
        self.assertEqual(code, 1)
        self.assertEqual(lines, [f"{self.dir}: script.toml: not found",
                                 f"FAIL {self.dir}: could not load"])

    def test_narration_writes_playback_order(self):
        code, lines = self.run_cli_cmd("narration", self.dir)
        self.assertEqual(code, 0)
        self.assertEqual(lines,
                         [f"{self.dir / 'narration.txt'}: wrote 37 lines"])
        self.assertEqual((self.dir / "narration.txt").read_text(encoding="utf-8"),
                         narration_text(load_contest(self.dir)))

    def test_narration_unloadable_contest(self):
        (self.dir / "script.toml").unlink()
        code, lines = self.run_cli_cmd("narration", self.dir)
        self.assertEqual(code, 1)
        self.assertEqual(lines, [f"{self.dir}: script.toml: not found",
                                 f"FAIL {self.dir}: could not load"])

    def test_module_entry_point(self):
        # Prop 2 itself, whose narration is current: the subprocess
        # lints a copy without one against the real speakability list.
        r = subprocess.run(
            [sys.executable, "-m", "ballotreels", "check",
             str(PROP_2)],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("PASS "))


class RenderCrashCourseTest(unittest.TestCase):
    """`render <election-dir>`: its crash course, in the formats asked for,
    each written as <id>-<format>.mp4 with its chapters. The film and the
    renderer are stand-ins: what is checked is what the command asks of
    them."""

    def render(self, *args):
        import tempfile

        import videobuilder as vb
        from videobuilder import render as vb_render

        from ballotreels import crash_course as cc

        film = vb.Film(draw=lambda n, cv: None, fps=30, frames=1,
                       formats=("9x16", "16x9"))
        module = mock.Mock(FILM=film, CHAPTERS=[{"start": 0.0, "title": "x"}])
        calls = []

        def fake_render(film_, dest, format=None, log=None):
            calls.append((Path(dest).name, getattr(format, "name", format)))

        out_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out_dir)
        out = io.StringIO()
        with mock.patch.object(vb, "load_module", return_value=module), \
                mock.patch.object(vb_render, "render", fake_render), \
                mock.patch.dict("os.environ"):
            code = main(["render", str(UT), "--out", str(out_dir), *args],
                        out=out)
        cid = cc.crash_course_id("ut-2026-11-03")
        return code, calls, cid, out_dir

    def test_16x9(self):
        code, calls, cid, out_dir = self.render("--format", "16x9")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(f"{cid}-16x9.mp4", "16x9")])
        self.assertTrue((out_dir / f"{cid}-16x9.chapters.json").is_file())

    def test_all_writes_both(self):
        code, calls, cid, _ = self.render("--format", "all")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(f"{cid}-9x16.mp4", "9x16"),
                                 (f"{cid}-16x9.mp4", "16x9")])

    def test_9x16_and_the_default_are_9x16_only(self):
        for args in (("--format", "9x16"), ()):
            code, calls, cid, _ = self.render(*args)
            self.assertEqual(code, 0)
            self.assertEqual(calls, [(f"{cid}-9x16.mp4", "9x16")], args)


if __name__ == "__main__":
    unittest.main()
