"""Deterministic drawing sounds for the sketchbook template: the real sound
of a pencil or a felt-tip marker moving on paper, cut from two short
recordings (`film/sounds/`, CC0 from BigSoundBank; see
`film/sounds/README.md`) rather than synthesized, since synthesized
graphite scratch never sounded like graphite. Which file plays for which
tool is the one line each in `TOOL_FILES`.

A sound covers exactly the frame span its `Item` is in contact with the
page (`measure.pencil_at`'s "current" case): nothing plays while the tool
only travels between two marks, or fades in or out at one. It is one fixed
rule for every stroke, so the YES and NO sections, whose visuals are
already identical in kind and size, sound alike (rule 4.2).

Each stroke takes a slice of its tool's recording as long as the stroke,
at an offset chosen deterministically from the stroke's own seed (so the
same script renders the same audio, byte for byte), with a short fade at
each end so a cut into the recording never clicks. A stroke longer than
the recording (a long illustration wipe) is built from several slices,
each its own offset, crossfaded end to end rather than looped audibly. The
recording's own texture carries the sound's character; only its level
follows the stroke's speed, and gently.

`build_track` mixes every stroke in a film's schedule into one buffer,
levelled so the strokes themselves (not the silence between them) sit
UNDER_VOICE_DB (13.5dB) under the RMS of the narration they are mixed
with (`narration_rms`), or, given no narration, under a typical one
(TARGET_RMS); `write_wav` and `sound_for` turn that into a cached WAV
file and a `vb.Sound` placed on the whole film.
"""
from __future__ import annotations

import hashlib
import math
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RATE = 24000               # the drawing-sound track's sample rate: both recordings already are
CONTROL_HZ = 200           # how densely a stroke's motion is sampled for speed
REF_SPEED = 550.0          # px/s a stroke at a "normal" pace moves; louder a little above it
FADE_S = 0.015             # a slice's own fade in/out, so a cut into the recording never clicks
XFADE_S = 0.08             # crossfade between successive slices on a stroke longer than the bed
UNDER_VOICE_DB = 13.5      # how far the strokes sit under the narration's RMS
TARGET_RMS = 0.0139        # the strokes' RMS with no narration given: ~13.5dB under a typical one (~0.066)
GAP_WINDOW_S = 0.01        # the window a recording's level is measured over for its gaps
GAP_DB = -20.0             # a window this far under the recording's median is the tool lifted off
GAP_MIN_S = 0.05           # ...and a run of such windows this long is a gap, cut out on load

# One recording per tool (film/sounds/, see film/sounds/README.md for each
# file's source and trim). The operator is auditioning other excerpts; try
# one by changing its line here.
TOOL_FILES = {
    'pencil': 'pencil.wav',            # bigsoundbank 3234-pencil-3, trimmed
    'highlighter': 'highlighter.wav',  # bigsoundbank 0220-marker, trimmed
}


def _rng(*parts):
    digest = hashlib.sha256('/'.join(str(p) for p in parts).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], 'big'))


def _load_recording(tool):
    path = HERE / 'sounds' / TOOL_FILES[tool]
    with wave.open(str(path), 'rb') as w:
        if w.getframerate() != RATE or w.getnchannels() != 1:
            raise ValueError(f'{path}: expected mono {RATE} Hz, got '
                             f'{w.getnchannels()}ch {w.getframerate()} Hz')
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
    return _drop_gaps(pcm.astype(np.float32) / 32768.0)


def _drop_gaps(rec):
    """`rec` with every stretch where the tool is off the paper cut out
    (at least GAP_MIN_S of windows GAP_DB or more under the recording's
    median level, like the marker lifting between sweeps), the pieces
    either side of each cut crossfaded over FADE_S, so any slice a stroke
    takes from it is the tool actually moving. Short dips (a pencil
    turning) stay: they are part of the texture."""
    w = max(1, int(round(RATE * GAP_WINDOW_S)))
    nwin = len(rec) // w
    if nwin == 0:
        return rec
    rms = np.sqrt((rec[:nwin * w].astype(np.float64).reshape(nwin, w) ** 2).mean(1))
    floor = np.median(rms) * 10 ** (GAP_DB / 20)
    quiet = np.append(rms < floor, False)
    min_run = max(1, int(round(GAP_MIN_S / GAP_WINDOW_S)))
    keep, run0 = [], None
    pos = 0
    for i, q in enumerate(quiet):
        if q and run0 is None:
            run0 = i
        elif not q and run0 is not None:
            # a run at the very start or end is trimmed whatever its length
            if i - run0 >= min_run or run0 == 0 or i == nwin:
                if run0 * w > pos:
                    keep.append(rec[pos:run0 * w])
                pos = i * w if i < nwin else len(rec)
            run0 = None
    if pos < len(rec):
        keep.append(rec[pos:])
    fade = max(1, int(round(RATE * FADE_S)))
    out = keep[0].copy()
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    for piece in keep[1:]:
        f = min(fade, len(out), len(piece))
        out[-f:] = out[-f:] * (1 - ramp[:f]) + piece[:f] * ramp[:f]
        out = np.concatenate([out, piece[f:]])
    return out.astype(np.float32)


_RECORDINGS = {tool: _load_recording(tool) for tool in TOOL_FILES}


def _bed_slice(tool, seed, n):
    """`n` samples cut from `tool`'s recording: one contiguous slice at a
    deterministic offset from `seed`, when the recording is at least that
    long. A longer stroke is built from several full, randomly rotated
    copies of the recording (each its own offset, from `seed` and its
    position), crossfaded end to end over XFADE_S, so it never repeats the
    same seam or loops audibly."""
    rec = _RECORDINGS[tool]
    rlen = len(rec)
    if n <= rlen:
        rng = _rng('draw-sound-bed', tool, seed, 0)
        start = int(rng.integers(0, rlen - n + 1))
        return rec[start:start + n].copy()
    xfade = max(1, min(int(round(RATE * XFADE_S)), rlen // 4))
    step = rlen - xfade
    nseg = 1 + math.ceil((n - rlen) / step)
    ramp = np.linspace(0, 1, xfade, dtype=np.float32)
    out = np.zeros(step * (nseg - 1) + rlen, np.float32)
    for k in range(nseg):
        rng = _rng('draw-sound-bed', tool, seed, k)
        seg = np.roll(rec, int(rng.integers(0, rlen)))
        a = k * step
        if k == 0:
            out[a:a + rlen] = seg
        else:
            out[a:a + xfade] = out[a:a + xfade] * (1 - ramp) + seg[:xfade] * ramp
            out[a + xfade:a + rlen] = seg[xfade:]
    return out[:n]


def _motion(head, f0, f1, steps):
    """`head(t)` sampled at `steps + 1` evenly spaced frames across
    f0..f1, as an array of (x, y) points."""
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
    steps = max(2, round(dur * CONTROL_HZ))
    pts = _motion(head, f0, f1, steps)
    vel = np.diff(pts, axis=0) * (fps * steps / max(1e-9, f1 - f0))
    speed = np.hypot(vel[:, 0], vel[:, 1])
    speed = np.concatenate([speed, speed[-1:]])
    t_audio = np.linspace(0, 1, n)
    t_ctrl = np.linspace(0, 1, steps + 1)
    speed_audio = np.interp(t_audio, t_ctrl, speed)
    # the level follows speed gently; the recording's own texture, not the
    # stroke's motion, carries everything else (no synthesized noise)
    norm = np.clip(speed_audio / REF_SPEED, 0.4, 2.2)
    amp = np.clip(norm ** 0.35, 0.65, 1.25)

    out = _bed_slice(tool, seed, n) * amp

    fade = max(1, round(RATE * FADE_S))
    if 2 * fade < n:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        out[:fade] *= ramp
        out[-fade:] *= ramp[::-1]
    return out.astype(np.float32)


def narration_rms(path):
    """The RMS (samples -1..1) of the 16-bit narration WAV at `path`, the
    level build_track sets the strokes under."""
    with wave.open(str(path), 'rb') as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
    if not len(pcm):
        return 0.0
    return float(np.sqrt(np.mean((pcm.astype(np.float64) / 32768.0) ** 2)))


def target_rms(voice_rms=None):
    """The strokes' RMS: UNDER_VOICE_DB under `voice_rms`, or TARGET_RMS
    when there is no narration level to follow."""
    if not voice_rms:
        return TARGET_RMS
    return voice_rms * 10 ** (-UNDER_VOICE_DB / 20)


def build_track(items, fps, total_frames, voice_rms=None):
    """The whole film's drawing-sound track: every scheduled item's stroke
    (an object with `.f0`, `.f1`, `.tool` and `.head(n)`, in
    `measure.pencil_at`'s sense) placed at its frame span and summed, then
    levelled so the strokes themselves sit at `target_rms(voice_rms)`:
    UNDER_VOICE_DB under the narration's RMS. Float32 samples at `RATE`."""
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
    active = buf[buf != 0]
    rms = float(np.sqrt(np.mean(active.astype(np.float64) ** 2))) if len(active) else 0.0
    if rms > 0:
        buf *= target_rms(voice_rms) / rms
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


def sound_for(items, fps, total_frames, cache_dir=None, voice_rms=None):
    """A `vb.Sound` of `build_track(items, fps, total_frames, voice_rms)`, written to
    a WAV under `cache_dir` (default: a system temp directory, never the
    contest or repo) named by the hash of its own samples, so the same
    script always yields the same file and a changed stroke (a new shape
    at the same timing, say) never reuses an earlier script's sound."""
    import videobuilder as vb

    samples = build_track(items, fps, total_frames, voice_rms)
    key = hashlib.sha256(samples.tobytes()).hexdigest()[:20]
    path = (Path(cache_dir) if cache_dir else _cache_dir()) / f'{key}.wav'
    if not path.is_file():
        write_wav(path, samples)
    return vb.Sound(path=str(path), at=0, start=0.0, frames=total_frames, gain_db=0.0,
                    fade_in_frames=0, fade_out_frames=0, ducks=False)
