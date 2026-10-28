"""Shared test helpers: a frozen Prop 2 contest, and broken copies of it."""

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
    synthesised afresh (narration.unreused_phrases)."""
    write_narration(contest_dir)
    path = Path(contest_dir) / "narration.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["phrase_cache"] = [{"key": {"text": p["text"]}}
                           for p in doc["phrases"]]
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (Path(contest_dir) / "narration.wav").write_bytes(b"")
