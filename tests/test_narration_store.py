"""A take's identity in narration.json (ballotreels.narration_store): what
`narration record` writes, and what "narrated" means once it is there."""

import hashlib
import io
import json
import shutil

from ballotreels.cli import main
from ballotreels.contest import load_contest
from ballotreels.index import key_for, key_string, load_index
from ballotreels.narration import CURRENT, MISSING, narration_state
from ballotreels.narration_store import (TAKE_KEY, Take, hash_file, record,
                                         recorded_take)
from ballotreels.standard import load_standard

from .helpers import NARRATION_SIDECARS, PROP_2, ContestCopyTestCase
from .test_crash_course import ElectionCopyTestCase


class RecordTest(ContestCopyTestCase):
    def setUp(self):
        super().setUp()
        for name in NARRATION_SIDECARS:
            shutil.copy2(PROP_2 / name, self.dir / name)
        doc = json.loads((self.dir / "narration.json").read_text("utf-8"))
        del doc[TAKE_KEY]
        (self.dir / "narration.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")

    def test_records_the_wav_bytes_hash(self):
        self.assertIsNone(recorded_take(self.dir))
        self.assertTrue(record(self.dir))
        wav = (self.dir / "narration.wav").read_bytes()
        self.assertEqual(recorded_take(self.dir),
                         Take(hashlib.sha256(wav).hexdigest(), len(wav)))
        self.assertEqual(hash_file(self.dir / "narration.wav"),
                         recorded_take(self.dir))

    def test_record_is_idempotent(self):
        record(self.dir)
        before = (self.dir / "narration.json").read_bytes()
        self.assertFalse(record(self.dir))
        self.assertEqual((self.dir / "narration.json").read_bytes(), before)

    def test_record_keeps_the_rest_of_the_sidecar(self):
        before = json.loads((self.dir / "narration.json").read_text("utf-8"))
        record(self.dir)
        after = json.loads((self.dir / "narration.json").read_text("utf-8"))
        self.assertEqual({k: v for k, v in after.items() if k != TAKE_KEY},
                         before)

    def test_a_new_take_is_recorded_again(self):
        record(self.dir)
        (self.dir / "narration.wav").write_bytes(b"RIFF another take")
        self.assertTrue(record(self.dir))
        self.assertEqual(recorded_take(self.dir).bytes, 17)

    def test_narrated_without_the_audio_once_recorded(self):
        (self.dir / "narration.wav").unlink()
        self.assertEqual(narration_state(load_contest(self.dir)), MISSING)
        shutil.copy2(PROP_2 / "narration.wav", self.dir / "narration.wav")
        record(self.dir)
        (self.dir / "narration.wav").unlink()
        self.assertEqual(narration_state(load_contest(self.dir)), CURRENT)

    def test_check_reports_an_unrecorded_take(self):
        out = io.StringIO()
        self.assertEqual(main(["check", str(self.dir)], out=out), 1)
        self.assertIn("narration-take: narration.json records no take; run "
                      "`python -m ballotreels narration record", out.getvalue())
        record(self.dir)
        out = io.StringIO()
        self.assertEqual(main(["check", str(self.dir)], out=out), 0,
                         out.getvalue())

    def test_a_malformed_take_is_no_take(self):
        doc = json.loads((self.dir / "narration.json").read_text("utf-8"))
        doc[TAKE_KEY] = {"sha256": "not-a-hash", "bytes": 3}
        (self.dir / "narration.json").write_text(json.dumps(doc), "utf-8")
        self.assertIsNone(recorded_take(self.dir))


class CrashCourseDigestTest(ElectionCopyTestCase):
    """A crash course's key reads a member's take from narration.json
    (narration.wav's own SHA-256), so it is the same with or without the
    audio in the checkout."""

    def key(self):
        index = load_index(self.dir)
        return key_string(key_for(index.election.id, index.crash_course,
                                  load_standard()))

    def test_same_key_with_or_without_the_wav(self):
        members = [self.dir / "amendment-a", self.dir / "amendment-b"]
        for d in members:
            doc = json.loads((d / "narration.json").read_text("utf-8"))
            doc.pop(TAKE_KEY, None)
            (d / "narration.json").write_text(json.dumps(doc), "utf-8")
        unrecorded = self.key()
        for d in members:
            record(d)
        recorded = self.key()
        self.assertNotEqual(recorded, unrecorded)  # narration.json changed
        for d in members:
            (d / "narration.wav").unlink()
        self.assertEqual(self.key(), recorded)
