"""`python -m ballotreels narration record|push|fetch` against a test
serve tier, and scripts/narrate.sh recording each new take."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ballotreels.cli import main
from ballotreels.narration_store import TAKE_KEY, hash_file, recorded_take

from .helpers import NARRATION_SIDECARS, PROP_2, REPO
from .test_serve_private import ServerTestCaseWithConfig


class NarrationCommandsTest(ServerTestCaseWithConfig):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.cache = Path(tmp.name) / "cache"
        self.dirs = []
        # two contests whose takes are still beside their sidecars, as in
        # a checkout from before the store, recording no take yet
        for i, name in enumerate(("prop-2", "prop-3")):
            d = self.repo / "data" / "ca-2026-11-03" / name
            d.mkdir(parents=True)
            for f in NARRATION_SIDECARS:
                shutil.copy2(PROP_2 / f, d / f)
            doc = json.loads((d / "narration.json").read_text("utf-8"))
            del doc[TAKE_KEY]
            (d / "narration.json").write_text(json.dumps(doc), "utf-8")
            (d / "narration.wav").write_bytes(
                (PROP_2 / "narration.wav").read_bytes() + bytes([i]))
            self.dirs.append(d)
        self.env = mock.patch.dict(os.environ, {
            "BALLOTREELS_SERVER": f"http://127.0.0.1:{self.private_port}",
            "BALLOTREELS_TOKEN": "test-token"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = main(["narration", *argv, "--repo", str(self.repo)]
                    if argv[0] == "record" else
                    ["narration", *argv, "--repo", str(self.repo),
                     "--narration-cache", str(self.cache)], out=out, err=err)
        return code, out.getvalue() + err.getvalue()

    def stored(self, d):
        return self.data_dir / "narration" / f"{recorded_take(d).sha256}.wav"

    def test_migration_record_then_push_then_fetch(self):
        code, out = self.run_cli("record", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("recorded 2 take(s)", out)
        for d in self.dirs:
            self.assertEqual(recorded_take(d), hash_file(d / "narration.wav"))

        code, out = self.run_cli("record", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("recorded 0 take(s), 2 already recorded", out)

        code, out = self.run_cli("push", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("uploaded 2 take(s), 0 already on the server", out)
        for d in self.dirs:
            wav = (d / "narration.wav").read_bytes()
            self.assertEqual(self.stored(d).read_bytes(), wav)
            self.assertEqual(
                (self.cache / self.stored(d).name).read_bytes(), wav)

        code, out = self.run_cli("push", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("uploaded 0 take(s), 2 already on the server", out)

        # a fresh clone (or the history purge): only the sidecars
        for d in self.dirs:
            (d / "narration.wav").unlink()
        shutil.rmtree(self.cache)
        code, out = self.run_cli("fetch", str(self.dirs[0]))
        self.assertEqual(code, 0, out)
        self.assertIn("1 from the server", out)
        self.assertEqual(hash_file(self.dirs[0] / "narration.wav"),
                         recorded_take(self.dirs[0]))
        # the other from the cache alone, with no server to ask
        shutil.copy2(self.stored(self.dirs[1]),
                     self.cache / self.stored(self.dirs[1]).name)
        with mock.patch.dict(os.environ, {"BALLOTREELS_SERVER": "",
                                          "BALLOTREELS_TOKEN": ""}):
            code, out = self.run_cli("fetch", "--all")
        self.assertEqual(code, 0, out)
        self.assertIn("fetched 1 from the cache, 0 from the server, "
                      "1 already here", out)
        self.assertEqual(hash_file(self.dirs[1] / "narration.wav"),
                         recorded_take(self.dirs[1]))

    def test_record_after_the_purge_keeps_the_recorded_take(self):
        self.run_cli("record", "--all")
        before = recorded_take(self.dirs[0])
        (self.dirs[0] / "narration.wav").unlink()
        code, out = self.run_cli("record", "--all")
        self.assertEqual(code, 0, out)
        self.assertEqual(recorded_take(self.dirs[0]), before)

    def test_push_refuses_an_unrecorded_take(self):
        code, out = self.run_cli("push", str(self.dirs[0]))
        self.assertEqual(code, 1)
        self.assertIn("narration record", out)
        self.assertFalse((self.data_dir / "narration").exists()
                         and any((self.data_dir / "narration").iterdir()))

    def test_push_refuses_a_wav_that_is_not_the_recorded_take(self):
        self.run_cli("record", str(self.dirs[0]))
        (self.dirs[0] / "narration.wav").write_bytes(b"RIFF new take")
        code, out = self.run_cli("push", str(self.dirs[0]))
        self.assertEqual(code, 1)
        self.assertIn("is not the take narration.json records", out)

    def test_push_needs_a_server(self):
        self.run_cli("record", "--all")
        with mock.patch.dict(os.environ, {"BALLOTREELS_SERVER": ""}):
            code, out = self.run_cli("push", "--all")
        self.assertEqual(code, 2)
        self.assertIn("no server URL", out)

    def test_fetch_without_a_server_works_from_the_cache(self):
        self.run_cli("record", "--all")
        self.run_cli("push", str(self.dirs[0]))
        for d in self.dirs:
            (d / "narration.wav").unlink()
        cases = [
            ("token only", {"BALLOTREELS_SERVER": ""}),
            ("neither", {"BALLOTREELS_SERVER": "", "BALLOTREELS_TOKEN": ""}),
        ]
        for name, env in cases:
            with self.subTest(name), mock.patch.dict(os.environ, env):
                code, out = self.run_cli("fetch", str(self.dirs[0]))
                self.assertEqual(code, 0, out)
                self.assertIn("1 from the cache", out)
                (self.dirs[0] / "narration.wav").unlink()
                # a take not in the cache fails that contest alone
                code, out = self.run_cli("fetch", "--all")
                self.assertEqual(code, 1, out)
                self.assertIn(f"{self.dirs[1]}: narration take "
                              f"{recorded_take(self.dirs[1]).sha256} is not "
                              f"in the local cache", out)
                self.assertIn("no server was given", out)
                self.assertIn("fetched 1 from the cache", out)
                (self.dirs[0] / "narration.wav").unlink()

    def test_fetch_or_push_with_a_server_and_no_token_is_refused(self):
        self.run_cli("record", "--all")
        for action in ("fetch", "push"):
            with self.subTest(action), \
                    mock.patch.dict(os.environ, {"BALLOTREELS_TOKEN": ""}):
                code, out = self.run_cli(action, "--all")
                self.assertEqual(code, 2, out)
                self.assertIn("BALLOTREELS_TOKEN is not set", out)

    def test_fetch_of_a_take_nowhere_fails_naming_it(self):
        self.run_cli("record", str(self.dirs[0]))
        sha = recorded_take(self.dirs[0]).sha256
        (self.dirs[0] / "narration.wav").unlink()
        code, out = self.run_cli("fetch", str(self.dirs[0]))
        self.assertEqual(code, 1)
        self.assertIn(sha, out)
        self.assertIn("not on the server", out)

    def test_fetch_never_replaces_a_different_wav(self):
        self.run_cli("record", str(self.dirs[0]))
        (self.dirs[0] / "narration.wav").write_bytes(b"RIFF new take")
        code, out = self.run_cli("fetch", str(self.dirs[0]))
        self.assertEqual(code, 1)
        self.assertEqual((self.dirs[0] / "narration.wav").read_bytes(),
                         b"RIFF new take")

    def test_dirs_or_all(self):
        code, _ = self.run_cli("record")
        self.assertEqual(code, 2)
        code, _ = self.run_cli("record", "--all", str(self.dirs[0]))
        self.assertEqual(code, 2)

    def test_narration_txt_still_written(self):
        d = self.repo / "prop-2"
        shutil.copytree(PROP_2, d)
        (d / "narration.txt").unlink()
        self.assertEqual(main(["narration", str(d)], out=io.StringIO()), 0)
        self.assertTrue((d / "narration.txt").is_file())



FAKE_PYTHON = """#!/bin/sh
# Stands in for the .venv's python: `videobuilder say` writes a fake take
# and its sidecar, `ballotreels check` passes, the rest is the real thing.
if [ "$1 $2 $3" = "-m videobuilder say" ]; then
    while [ $# -gt 0 ]; do
        [ "$1" = "--out" ] && out=$2
        shift
    done
    printf 'RIFF a new take' > "$out"
    printf '{"phrases": [], "seconds": 0}\\n' > "${out%.wav}.json"
    exit 0
fi
if [ "$1 $2 $3" = "-m ballotreels check" ]; then
    exit 0
fi
PYTHONPATH=@REPO@ exec @PYTHON@ -B "$@"
"""


class NarrateScriptRecordsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = repo = Path(tmp.name)
        (repo / "scripts").mkdir()
        shutil.copy2(REPO / "scripts" / "narrate.sh", repo / "scripts")
        (repo / "voices").mkdir()
        (repo / "voices" / "narration-style.txt").write_text("calm\n")
        python = repo / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text(FAKE_PYTHON.replace("@REPO@", str(REPO))
                          .replace("@PYTHON@", sys.executable))
        python.chmod(0o755)
        self.dir = repo / "prop-2"
        shutil.copytree(PROP_2, self.dir,
                        ignore=shutil.ignore_patterns(*NARRATION_SIDECARS))
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("BALLOTREELS_SERVER", "BALLOTREELS_TOKEN")}
        self.env["BALLOTREELS_NARRATION_CACHE"] = str(repo / "cache")

    def narrate(self):
        return subprocess.run(
            ["bash", str(self.repo / "scripts" / "narrate.sh"),
             str(self.dir)],
            capture_output=True, text=True, env=self.env, timeout=120)

    def test_a_new_take_is_recorded(self):
        result = self.narrate()
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)
        d = self.dir
        self.assertEqual(recorded_take(d), hash_file(d / "narration.wav"))
        self.assertEqual(recorded_take(d).bytes, len(b"RIFF a new take"))

    def test_a_failed_fetch_still_narrates(self):
        # a take recorded, then a `say` interrupted after writing new
        # audio: the WAV left beside narration.json is not its take
        self.assertEqual(self.narrate().returncode, 0)
        d = self.dir
        (d / "narration.wav").write_bytes(b"RIFF half a take")
        cases = [
            ("a leftover WAV", {}),
            ("a server and no token",
             {"BALLOTREELS_SERVER": "http://127.0.0.1:9"}),
        ]
        for name, env in cases:
            with self.subTest(name):
                self.env.update(env)
                result = self.narrate()
                self.assertEqual(result.returncode, 0,
                                 result.stdout + result.stderr)
                self.assertIn(f"{d}: could not fetch its recorded take",
                              result.stderr)
                self.assertEqual(recorded_take(d),
                                 hash_file(d / "narration.wav"))
                (d / "narration.wav").write_bytes(b"RIFF half a take")
