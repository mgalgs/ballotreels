"""Shared test helpers: the real Prop 2 contest, and broken copies of it."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROP_2 = REPO / "data" / "ca-2026-11-03" / "prop-2"


class ContestCopyTestCase(unittest.TestCase):
    """Gives each test a scratch copy of Prop 2 to break."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "prop-2"
        shutil.copytree(PROP_2, self.dir)

    def edit(self, name, old, new, count=1):
        """Replace `old` with `new` in the copy's file `name`.

        Fails the test if `old` does not occur exactly `count` times, so a
        change to the real data cannot silently turn a test into a no-op.
        """
        path = self.dir / name
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), count,
                         f"{old!r} occurs {text.count(old)} times in {name}")
        path.write_text(text.replace(old, new), encoding="utf-8")


def drop_background(contest_dir):
    """Remove every background section from `contest_dir`'s script.toml."""
    path = Path(contest_dir) / "script.toml"
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r'\[\[section\]\]\nid = "background"\n.*?'
                     r'(?=\[\[section\]\]\nid = "today")',
                     "", text, flags=re.DOTALL)
    assert n == 1 and new.count('id = "background"') == 0, "no background"
    path.write_text(new, encoding="utf-8")
