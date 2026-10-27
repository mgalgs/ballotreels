"""film/draw_sound.py: the drawing sounds render byte-for-byte the same
from the same stroke motion, play only while a stroke is on the page, and
sit at their intended level under the narration."""

import sys
import unittest
import wave
from pathlib import Path

import numpy as np

from .helpers import REPO

sys.path.insert(0, str(REPO / "film"))
import draw_sound as ds  # noqa: E402


class Stroke:
    """A fake Item: a straight line from `a` to `b`, with a sharp corner
    partway if `corner` is given."""

    def __init__(self, f0, f1, tool, a, b, corner=None):
        self.f0, self.f1, self.tool = f0, f1, tool
        self.a, self.b, self.corner = a, b, corner

    def head(self, t):
        p = min(1.0, max(0.0, (t - self.f0) / (self.f1 - self.f0)))
        if self.corner is not None and p < 0.5:
            a, b, q = self.a, self.corner, p / 0.5
        elif self.corner is not None:
            a, b, q = self.corner, self.b, (p - 0.5) / 0.5
        else:
            a, b, q = self.a, self.b, p
        return a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q


class StrokeTrackTest(unittest.TestCase):
    def test_deterministic(self):
        s = Stroke(0, 15, "pencil", (100, 100), (500, 100))
        a = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, "seed-1")
        b = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, "seed-1")
        self.assertTrue((a == b).all())
        self.assertGreater(len(a), 0)

    def test_different_seed_differs(self):
        s = Stroke(0, 15, "pencil", (100, 100), (500, 100))
        a = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, "seed-1")
        b = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, "seed-2")
        self.assertFalse((a == b).all())

    def test_pencil_and_highlighter_differ(self):
        s = Stroke(0, 15, "pencil", (100, 100), (500, 100))
        pencil = ds.stroke_track(s.head, s.f0, s.f1, 30, "pencil", 0)
        hi = ds.stroke_track(s.head, s.f0, s.f1, 30, "highlighter", 0)
        self.assertEqual(len(pencil), len(hi))
        self.assertFalse((pencil == hi).all())

    def test_too_short_is_silent(self):
        s = Stroke(0, 0.001, "pencil", (100, 100), (110, 100))
        out = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, 0)
        self.assertEqual(len(out), 0)

    def test_finite_and_bounded(self):
        s = Stroke(0, 20, "pencil", (100, 100), (600, 400), corner=(550, 100))
        out = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, 0)
        self.assertTrue(np.isfinite(out).all())
        self.assertLess(float(np.abs(out).max()), 2.0)

    def test_a_faster_stroke_is_louder(self):
        slow = Stroke(0, 60, "pencil", (100, 100), (200, 100))
        fast = Stroke(0, 10, "pencil", (100, 100), (900, 100))
        slow_out = ds.stroke_track(slow.head, slow.f0, slow.f1, 30, "pencil", 0)
        fast_out = ds.stroke_track(fast.head, fast.f0, fast.f1, 30, "pencil", 0)
        rms = lambda x: (x.astype("float64") ** 2).mean() ** 0.5  # noqa: E731
        self.assertGreater(rms(fast_out), rms(slow_out) * 1.3)

    def test_a_stroke_longer_than_the_recording_is_still_deterministic(self):
        # the bed recordings are a few seconds; a stroke many times that
        # long exercises the crossfaded-slices path, not a single slice
        bed_s = len(ds._RECORDINGS["pencil"]) / ds.RATE
        frames = round(bed_s * 3 * 30)
        s = Stroke(0, frames, "pencil", (100, 100), (900, 900))
        a = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, "seed-1")
        b = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, "seed-1")
        self.assertTrue((a == b).all())
        self.assertEqual(len(a), round(frames / 30 * ds.RATE))
        self.assertTrue(np.isfinite(a).all())
        self.assertLess(float(np.abs(a).max()), 2.0)


class BuildTrackTest(unittest.TestCase):
    def test_deterministic(self):
        items = [Stroke(0, 15, "pencil", (100, 100), (500, 100)),
                 Stroke(20, 40, "highlighter", (50, 50), (50, 300))]
        a = ds.build_track(items, 30, 60)
        b = ds.build_track(items, 30, 60)
        self.assertTrue((a == b).all())

    def test_silent_with_no_items(self):
        out = ds.build_track([], 30, 60)
        self.assertEqual(float(np.abs(out).max()), 0.0)

    def test_silent_outside_the_strokes(self):
        # a gap between two strokes, and a hold after the last one: both
        # frame spans play nothing, since the tool is not drawing
        items = [Stroke(10, 20, "pencil", (100, 100), (300, 100)),
                 Stroke(40, 55, "highlighter", (50, 50), (50, 300))]
        out = ds.build_track(items, 30, 90)
        gap = out[round(21 / 30 * ds.RATE):round(39 / 30 * ds.RATE)]
        tail = out[round(56 / 30 * ds.RATE):]
        self.assertEqual(float(np.abs(gap).max()), 0.0)
        self.assertEqual(float(np.abs(tail).max()), 0.0)

    def test_level_is_well_under_the_narration(self):
        # the strokes themselves (ignoring the silence between them) sit
        # close to TARGET_RMS, calibrated against the committed Prop 2
        # narration's RMS (helpers.NARRATION_RMS): about 12-15dB under it
        import math

        from .helpers import NARRATION_RMS
        items = [Stroke(0, 20, "pencil", (100, 100), (600, 100)),
                 Stroke(30, 60, "highlighter", (50, 50), (50, 400))]
        out = ds.build_track(items, 30, 90)
        active = out[out != 0]
        rms = float(np.sqrt(np.mean(active.astype("float64") ** 2)))
        self.assertAlmostEqual(rms, ds.TARGET_RMS, delta=ds.TARGET_RMS * 0.05)
        down_db = 20 * math.log10(NARRATION_RMS / rms)
        self.assertGreaterEqual(down_db, 12.0)
        self.assertLessEqual(down_db, 15.0)

    def test_write_wav_round_trips_the_sample_count(self):
        items = [Stroke(0, 15, "pencil", (100, 100), (500, 100))]
        track = ds.build_track(items, 30, 30)
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "draw-sound.wav"
        ds.write_wav(path, track)
        with wave.open(str(path), "rb") as w:
            self.assertEqual(w.getnframes(), len(track))
            self.assertEqual(w.getframerate(), ds.RATE)
            self.assertEqual(w.getnchannels(), 1)

    def test_sound_for_caches_by_content_not_timing(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        slow = [Stroke(0, 15, "pencil", (100, 100), (140, 100))]
        fast = [Stroke(0, 15, "pencil", (100, 100), (900, 100))]
        a = ds.sound_for(slow, 30, 30, cache_dir=tmp)
        b = ds.sound_for(fast, 30, 30, cache_dir=tmp)
        again = ds.sound_for(slow, 30, 30, cache_dir=tmp)
        self.assertNotEqual(a.path, b.path)
        self.assertEqual(a.path, again.path)


if __name__ == "__main__":
    unittest.main()
