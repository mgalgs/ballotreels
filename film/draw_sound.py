"""Deterministic drawing sounds for the sketchbook template: a soft, dry
graphite scratch while the pencil draws, a softer felt-tip swish while the
highlighter sweeps (film/measure.py's `page` visual). Neither sound is in
the bundled sound bank (`vb.sfx`) and the sandbox has no network, so both
are synthesized here from the stroke's own motion (shaped, filtered noise
with a bit of paper grain), seeded from the stroke's own timing and tool so
the same script renders the same audio, byte for byte.

A sound covers exactly the frame span its `Item` is in contact with the
page (`measure.pencil_at`'s "current" case): nothing plays while the tool
only travels between two marks, or fades in or out at one. It is one fixed
rule for every stroke, so the YES and NO sections, whose visuals are
already identical in kind and size, sound alike (rule 4.2).

`build_track` mixes every stroke in a film's schedule into one buffer;
`write_wav` and `sound_for` turn that into a cached WAV file and a
`vb.Sound` placed on the whole film.
"""
from __future__ import annotations

import hashlib
import math
import tempfile
import wave
from pathlib import Path

import numpy as np

RATE = 24000               # the drawing-sound track's sample rate
CONTROL_HZ = 200           # how densely a stroke's motion is sampled for speed and corners
REF_SPEED = 550.0          # px/s a stroke at a "normal" pace moves; louder and brighter above it
CORNER_ANGLE = math.radians(55)   # a turn sharper than this, at speed, gets a tick
TICK_MS = 18
FADE_S = 0.004             # a stroke's own fade in/out, so it never clicks on or off
TARGET_PEAK = 0.16         # the whole track's peak, well under the narration's

# Each tool's noise band (Hz): a dark half and a bright half, cross-faded by
# speed, plus whether it carries graphite's grain (an amplitude flutter).
TOOLS = {
    'pencil': dict(lo=1300, mid=2800, hi=5400, grain=True),
    'highlighter': dict(lo=450, mid=1100, hi=2100, grain=False),
}


def _rng(*parts):
    digest = hashlib.sha256('/'.join(str(p) for p in parts).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], 'big'))


def _band_noise(n, rng, lo, hi, rate=RATE):
    """`n` samples of noise with energy only between `lo` and `hi` Hz (a
    soft-edged band, built in the frequency domain so it needs no filter
    design), peak-normalised to 1."""
    if n <= 0:
        return np.zeros(0, np.float32)
    spec = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / rate)
    edge = max(1.0, (hi - lo) * 0.3)
    mask = np.clip(np.minimum((freqs - lo) / edge, (hi - freqs) / edge), 0, 1)
    out = np.fft.irfft(spec * mask, n).astype(np.float32)
    peak = float(np.abs(out).max())
    return out / peak if peak > 0 else out


def _motion(head, f0, f1, steps):
    """(points, speed) of `head(t)` sampled at `steps + 1` frames across
    f0..f1: speed is px/s between consecutive samples, one shorter than
    points, padded to match by repeating its last value."""
    ts = np.linspace(f0, f1, steps + 1)
    pts = np.array([head(t) for t in ts], np.float64)
    return pts


def stroke_track(head, f0, f1, fps, tool, seed):
    """The drawing sound for one stroke, from frame `f0` to `f1`: `head(t)`
    is the tool's tip at frame `t` (fractional frames allowed), exactly
    what `measure.Item.head` gives the pencil sprite to follow. `seed`
    makes two strokes with the same span and tool (which cannot both occur
    in one render) sound identically, and everything else sound
    differently. Float32 samples at `RATE`, -1..1; empty if the span is
    too short to hear."""
    dur = (f1 - f0) / fps
    n = int(round(dur * RATE))
    if n < 8:
        return np.zeros(0, np.float32)
    cfg = TOOLS[tool]
    rng = _rng('draw-sound', tool, seed, round(f0, 3), round(f1, 3))
    steps = max(2, round(dur * CONTROL_HZ))
    pts = _motion(head, f0, f1, steps)
    vel = np.diff(pts, axis=0) * (fps * steps / max(1e-9, f1 - f0))
    speed = np.hypot(vel[:, 0], vel[:, 1])
    speed = np.concatenate([speed, speed[-1:]])
    t_audio = np.linspace(0, 1, n)
    t_ctrl = np.linspace(0, 1, steps + 1)
    speed_audio = np.interp(t_audio, t_ctrl, speed)
    norm = np.clip(speed_audio / REF_SPEED, 0.15, 2.6)
    amp = np.clip(norm ** 0.5, 0.35, 1.4)
    bright = np.clip((norm - 0.3) / 2.0, 0.0, 1.0)

    dark = _band_noise(n, rng, cfg['lo'], cfg['mid'])
    light = _band_noise(n, rng, cfg['mid'], cfg['hi'])
    out = (dark * (1 - bright) + light * bright) * amp
    if cfg['grain']:
        grain = _band_noise(n, rng, 70, 170)
        out *= np.clip(0.6 + 0.75 * np.abs(grain), 0.45, 1.25)

    if steps >= 2:
        v = np.diff(pts, axis=0)
        mags = np.hypot(v[:, 0], v[:, 1])
        tick_n = max(1, round(RATE * TICK_MS / 1000))
        decay = np.exp(-np.linspace(0, 7, tick_n))
        for i in range(1, len(v)):
            if mags[i - 1] < 1.0 or mags[i] < 1.0:
                continue
            cos_a = np.dot(v[i - 1], v[i]) / (mags[i - 1] * mags[i])
            if math.acos(np.clip(cos_a, -1.0, 1.0)) <= CORNER_ANGLE:
                continue
            c = int(round((i / steps) * n))
            tick = _band_noise(tick_n, rng, cfg['hi'] * 0.55, cfg['hi'] * 1.5) * decay
            a0, a1 = max(0, c), min(n, c + tick_n)
            if a1 > a0:
                out[a0:a1] += tick[:a1 - a0] * 0.55

    fade = max(1, round(RATE * FADE_S))
    if 2 * fade < n:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        out[:fade] *= ramp
        out[-fade:] *= ramp[::-1]
    # left at its `amp`-scaled level, not renormalised to its own peak, so a
    # fast stroke is louder than a slow one once build_track mixes them;
    # only the whole track's peak is brought down, by build_track.
    return out.astype(np.float32)


def build_track(items, fps, total_frames):
    """The whole film's drawing-sound track: every scheduled item's stroke
    (an object with `.f0`, `.f1`, `.tool` and `.head(n)`, in
    `measure.pencil_at`'s sense) placed at its frame span and summed, then
    brought to `TARGET_PEAK`. Float32 samples at `RATE`."""
    n_total = max(1, int(round(total_frames / fps * RATE)))
    buf = np.zeros(n_total, np.float32)
    for i, it in enumerate(items):
        clip = stroke_track(it.head, it.f0, it.f1, fps, it.tool, i)
        if not len(clip):
            continue
        start = int(round(it.f0 / fps * RATE))
        a, b = max(0, start), min(n_total, start + len(clip))
        if b > a:
            buf[a:b] += clip[a - start:b - start]
    peak = float(np.abs(buf).max())
    if peak > TARGET_PEAK:
        buf *= TARGET_PEAK / peak
    return buf


def write_wav(path, samples, rate=RATE):
    """`samples` (float32, -1..1) as a mono 16-bit PCM WAV at `path`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def _cache_dir():
    return Path(tempfile.gettempdir()) / 'ballotreels-draw-sound'


def sound_for(items, fps, total_frames, cache_dir=None):
    """A `vb.Sound` of `build_track(items, fps, total_frames)`, written once
    to a content-addressed WAV under `cache_dir` (default: a system temp
    directory, never the contest or repo) and reused by its hash on a
    later call with the same items, so re-rendering the same script is
    byte-for-byte the same without resynthesising it."""
    import videobuilder as vb

    key = hashlib.sha256(
        repr([(round(it.f0, 3), round(it.f1, 3), it.tool) for it in items]).encode()
    ).hexdigest()[:20]
    path = (Path(cache_dir) if cache_dir else _cache_dir()) / f'{key}.wav'
    if not path.is_file():
        write_wav(path, build_track(items, fps, total_frames))
    return vb.Sound(path=str(path), at=0, start=0.0, frames=total_frames, gain_db=0.0,
                    fade_in_frames=0, fade_out_frames=0, ducks=False)
