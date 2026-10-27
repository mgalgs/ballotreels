"""film/draw_sound.py: the drawing sounds render byte-for-byte the same
from the same stroke motion, and stay under their target level."""

import sys
import unittest
import wave

import numpy as np

from .helpers import REPO

sys.path.insert(0, str(REPO / "film"))
import draw_sound as ds  # noqa: E402


class Stroke:
    """A fake Item: a straight line from `a` to `b`, with a sharp corner
    partway if `corner` is given (so the tick-detection path runs too)."""

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
        self.assertFalse((pencil == hi).all())

    def test_too_short_is_silent(self):
        s = Stroke(0, 0.001, "pencil", (100, 100), (110, 100))
        out = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, 0)
        self.assertEqual(len(out), 0)

    def test_finite_and_bounded(self):
        s = Stroke(0, 20, "pencil", (100, 100), (600, 400), corner=(550, 100))
        out = ds.stroke_track(s.head, s.f0, s.f1, 30, s.tool, 0)
        self.assertTrue(np.isfinite(out).all())
        self.assertLess(float(abs(out).max()), 10.0)

    def test_a_faster_stroke_is_louder_and_brighter(self):
        slow = Stroke(0, 60, "pencil", (100, 100), (200, 100))
        fast = Stroke(0, 10, "pencil", (100, 100), (900, 100))
        slow_out = ds.stroke_track(slow.head, slow.f0, slow.f1, 30, "pencil", 0)
        fast_out = ds.stroke_track(fast.head, fast.f0, fast.f1, 30, "pencil", 0)
        rms = lambda x: (x.astype("float64") ** 2).mean() ** 0.5  # noqa: E731

        def treble(x):  # the share of the energy above 4 kHz
            spec = np.abs(np.fft.rfft(x.astype("float64"))) ** 2
            return spec[np.fft.rfftfreq(len(x), 1 / ds.RATE) > 4000].sum() / spec.sum()
        # the clips are not normalised, so the speed shows in the level
        self.assertGreater(rms(fast_out), rms(slow_out) * 2)
        self.assertGreater(treble(fast_out), treble(slow_out) + 0.2)


class BuildTrackTest(unittest.TestCase):
    def test_deterministic_and_under_target_peak(self):
        items = [Stroke(0, 15, "pencil", (100, 100), (500, 100)),
                 Stroke(20, 40, "highlighter", (50, 50), (50, 300))]
        a = ds.build_track(items, 30, 60)
        b = ds.build_track(items, 30, 60)
        self.assertTrue((a == b).all())
        self.assertLessEqual(float(abs(a).max()), ds.TARGET_PEAK + 1e-6)

    def test_silent_with_no_items(self):
        out = ds.build_track([], 30, 60)
        self.assertEqual(float(abs(out).max()), 0.0)

    def test_write_wav_round_trips_the_sample_count(self):
        items = [Stroke(0, 15, "pencil", (100, 100), (500, 100))]
        track = ds.build_track(items, 30, 30)
        path = REPO / ".test-scratch-draw-sound.wav"
        self.addCleanup(lambda: path.unlink(missing_ok=True))
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
