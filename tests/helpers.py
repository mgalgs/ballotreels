"""Shared test helpers: a frozen Prop 2 contest, and broken copies of it."""

import functools
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# A frozen copy of Prop 2, not the live data/ contest: tests edit exact
# strings in its script, so the live script stays free to change.
PROP_2 = REPO / "tests" / "fixtures" / "prop-2"


# The real Prop 2 narration was read in 23.3 s (yes) and 24.7 s (no): within
# the 2s pad cap, so check_airtime pads it rather than failing.

# A typical narration's RMS (16-bit samples -1..1): what
# film/draw_sound.py's TARGET_RMS (its level when no narration is given)
# sits about 13.5dB under. Measured from two recent narrations (recipes e60-story and
# e60b-breathe, 0.0663 and 0.0653); the committed Prop 2 narration.wav
# is an outlier at 0.1252, from an earlier TTS pass with louder
# normalisation, so it is not used here.
NARRATION_RMS = 0.0658

NARRATION_SIDECARS = ("narration.json", "narration.wav", "narration.vtt")


@functools.cache
def unlinted_standard():
    """The standard with an empty speakability list. A copy of Prop 2
    without its sidecars has no narration, so every line is fresh and
    linted; a test of some other check's exact failures uses this so it
    does not depend on what standard/speakability.txt lists."""
    from dataclasses import replace

    from ballotreels.standard import load_standard
    return replace(load_standard(), speakability=())


class ContestCopyTestCase(unittest.TestCase):
    """Gives each test a scratch copy of Prop 2 to break, without its
    narration sidecars: a test that needs them writes stand-ins with
    write_narration."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "prop-2"
        shutil.copytree(PROP_2, self.dir,
                        ignore=shutil.ignore_patterns(*NARRATION_SIDECARS))

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


def write_narration(contest_dir, stretch=None):
    """Write a stand-in narration.json for `contest_dir`'s current script,
    as `videobuilder say` would lay it out: each phrase 0.4s per word, 0.25s
    apart. `stretch` maps a section label to a factor on its phrases'
    lengths. The real sidecars are made on the host with a TTS model; these
    only exercise the phrase<->line mapping and the airtime check."""
    from videobuilder import speech

    from ballotreels.contest import load_contest
    from ballotreels.narration import narration_lines

    stretch = stretch or {}
    phrases = []
    t = 0.0
    for line in narration_lines(load_contest(contest_dir)):
        for text in speech.phrases(line.text):
            end = t + 0.4 * len(text.split()) * stretch.get(line.section, 1)
            phrases.append({"text": text, "start": round(t, 2),
                            "end": round(end, 2)})
            t = end + 0.25
    doc = {"phrases": phrases, "seconds": round(t, 2)}
    (Path(contest_dir) / "narration.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def write_committed_narration(contest_dir):
    """Stand in for a narration committed for `contest_dir`'s current
    script: write_narration's narration.json, with a phrase_cache keyed as
    `say` records one, beside an empty narration.wav. Editing a line
    afterwards leaves only its phrases, and the phrase after them, to be
    synthesised afresh (narration.unreused_phrases). Its take is recorded
    in narration.json, as `narration record` records one."""
    write_narration(contest_dir)
    path = Path(contest_dir) / "narration.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["phrase_cache"] = [{"key": {"text": p["text"]}}
                           for p in doc["phrases"]]
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (Path(contest_dir) / "narration.wav").write_bytes(b"")
    from ballotreels.narration_store import record
    record(contest_dir)


def git_commit_all(repo, message="fixture"):
    """Commit everything in `repo` (made a git repo if it is not one yet)
    and return the commit's sha: the worker renders from committed HEAD
    only, so a test's edit to a fake repo counts once committed."""
    import subprocess
    repo = Path(repo)

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=test",
             "-c", "user.email=test@example.org", "-c", "commit.gpgsign=false",
             *args], check=True, capture_output=True).stdout.decode().strip()

    if not (repo / ".git").exists():
        git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", message)
    return git("rev-parse", "HEAD")


def write_take(contest_dir, rms=NARRATION_RMS):
    """Stand in for the take `contest_dir`'s narration.json records, whose
    audio is not in git (narration_store): a tone as long as its
    `seconds`, at a typical narration's level, written to narration.wav
    and recorded as the take. Only ever in a scratch copy."""
    import array
    import math
    import sys
    import wave

    from ballotreels.narration_store import record

    contest_dir = Path(contest_dir)
    doc = json.loads((contest_dir / "narration.json").read_text(
        encoding="utf-8"))
    rate, period = 24000, 120  # 200 Hz, a whole number of samples a cycle
    amp = rms * math.sqrt(2) * 32767
    cycle = array.array("h", (round(amp * math.sin(2 * math.pi * i / period))
                              for i in range(period)))
    n = round(doc["seconds"] * rate)
    pcm = cycle * (n // period) + cycle[:n % period]
    if sys.byteorder == "big":
        pcm.byteswap()
    with wave.open(str(contest_dir / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    record(contest_dir)


def copy_contest(src, dest):
    """Copy the contest directory `src` to `dest`, giving the copy a
    stand-in for its recorded take (write_take) in place of the audio,
    which git does not hold: never the checkout's own narration.wav, so
    the copy is the same with or without one there."""
    from ballotreels.narration_store import recorded_take

    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("narration.wav"))
    if recorded_take(dest) is not None:
        write_take(dest)
    return Path(dest)


def copy_election(src, dest, contests=None):
    """Copy the election directory `src` to `dest`: its own files, and
    each contest directory (only those named in `contests`, when given)
    by copy_contest."""
    src, dest = Path(src), Path(dest)
    dest.mkdir(parents=True)
    for path in sorted(src.iterdir()):
        if not path.is_dir():
            shutil.copy2(path, dest / path.name)
        elif contests is None or path.name in contests:
            copy_contest(path, dest / path.name)
    return dest


FILM_CONTEST = REPO / "data" / "ca-2026-11-03" / "prop-2"
_film_dir = None


@functools.cache
def film_measure():
    """film/measure.py, as `from film import measure` imports it, for its
    default contest (live Prop 2): read from a scratch copy (copy_contest),
    whose stand-in take the film reads at import for its level, since the
    real audio is not in the checkout. Every test's `film.measure` is this
    one."""
    import importlib
    import os
    import sys

    global _film_dir
    assert "film.measure" not in sys.modules, "film.measure imported first"
    # kept for the whole run: the module plays VOICE.path whenever asked
    _film_dir = tempfile.TemporaryDirectory()
    contest = copy_contest(FILM_CONTEST, Path(_film_dir.name) /
                           FILM_CONTEST.parent.name / FILM_CONTEST.name)
    old = os.environ.get("BALLOTREELS_CONTEST")
    os.environ["BALLOTREELS_CONTEST"] = str(contest)
    try:
        return importlib.import_module("film.measure")
    finally:
        if old is None:
            del os.environ["BALLOTREELS_CONTEST"]
        else:
            os.environ["BALLOTREELS_CONTEST"] = old
