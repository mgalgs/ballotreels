import re
import unittest

from .helpers import REPO

README = (REPO / "README.md").read_text(encoding="utf-8")
ARCHITECTURE = (REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")

# Files whose flags and env vars README.md must document. BALLOTREELS_CONTEST
# and BALLOTREELS_CRASH_COURSE (set by cli.py, read by film/measure.py and
# film/crash_course.py) are deliberately excluded: they are internal signals
# to the render templates, not user-facing options.
SCANNED_FILES = ("ballotreels/cli.py", "ballotreels/site/config.py",
                 "ballotreels/worker.py", "ballotreels/storage.py")
EXCLUDED_ENV_VARS = {"BALLOTREELS_CONTEST", "BALLOTREELS_CRASH_COURSE"}

FLAG_RE = re.compile(r'"(--[a-z][a-z0-9-]*)"')
ENV_RE = re.compile(r"BALLOTREELS_[A-Z0-9_]+")


class ReadmeDocumentsEveryOptionTest(unittest.TestCase):
    def test_readme_documents_every_option(self):
        flags = set()
        env_vars = set()
        for relpath in SCANNED_FILES:
            text = (REPO / relpath).read_text(encoding="utf-8")
            flags.update(FLAG_RE.findall(text))
            env_vars.update(ENV_RE.findall(text))
        env_vars -= EXCLUDED_ENV_VARS

        missing_flags = sorted(f for f in flags if f not in README)
        missing_env = sorted(e for e in env_vars if e not in README)
        self.assertEqual(missing_flags, [], "flags missing from README.md")
        self.assertEqual(missing_env, [], "env vars missing from README.md")


class ArchitectureScopeUpdatedTest(unittest.TestCase):
    def test_architecture_scope_updated(self):
        self.assertNotIn("Single user, run locally", ARCHITECTURE)
        for needle in ("serve tier", "worker", "queue monitor",
                      "bearer token"):
            self.assertIn(needle, ARCHITECTURE)


if __name__ == "__main__":
    unittest.main()
