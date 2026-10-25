import io
import subprocess
import sys
import unittest

from ballotreels.cli import main
from ballotreels.contest import load_contest
from ballotreels.narration import narration_text

from .helpers import PROP_2, REPO, ContestCopyTestCase


class CliTest(ContestCopyTestCase):
    def run_cli_cmd(self, command, *dirs):
        out = io.StringIO()
        code = main([command, *map(str, dirs)], out=out)
        return code, out.getvalue().splitlines()

    def run_cli(self, *dirs):
        return self.run_cli_cmd("check", *dirs)

    def test_prop_2_passes(self):
        code, lines = self.run_cli(PROP_2)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "PASS ca-2026-11-03-prop-2; words what=41 background[0]=70 "
            "background[1]=74 background[2]=52 background[3]=27 today=81 "
            "change=97 fiscal=49 yes=79 no=79 vote=43; no plays first"])

    def test_failures_one_per_line(self):
        self.edit("script.toml", "standard_version = 2",
                  "standard_version = 0")
        self.edit("script.toml", "The Legislature put it",
                  "The bold Legislature put it")
        code, lines = self.run_cli(PROP_2, self.dir)
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
        r = subprocess.run(
            [sys.executable, "-m", "ballotreels", "check",
             "data/ca-2026-11-03/prop-2"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("PASS "))


if __name__ == "__main__":
    unittest.main()
