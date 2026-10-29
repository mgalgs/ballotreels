"""Narration: script lines in playback order, and the sidecar phrases
`videobuilder`'s `say` produced from them.

Playback order is the measure template's section order (docs/SCRIPT-FORMAT.md),
background sections in file order, with its two side sections reordered by
`side_order` (STANDARD.md rule 2.4):
the order `python -m ballotreels narration` writes to `narration.txt`, and the
order the renderer narrates in.

`say` splits each line into one or more *phrases* (it splits on sentence
boundaries), so a line and a phrase aren't the same thing: `match_phrases`
maps the committed `narration.json`'s phrases back to the script lines that
produced them, by re-splitting each line's text the same way `say` does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contest import Contest, Section
from .standard import side_order, template_for


class NarrationError(Exception):
    """The committed narration sidecars don't match the current script."""


@dataclass(frozen=True)
class NarrationLine:
    section: str  # the section's label (Script.labels)
    index: int  # 0-based index into that section's lines
    text: str


@dataclass(frozen=True)
class NarrationSpan:
    """Where one script line falls on the narration audio's clock."""
    section: str
    index: int
    start: float
    end: float


def playback_sections(contest: Contest) -> tuple[tuple[str, Section], ...]:
    """(label, section) pairs in narration/playback order: the template's
    order, each slot taking the script's sections with that id in file order
    (so template 2's background sections play as written), with the two side
    sections reordered by `side_order`. Sections the template doesn't name
    are left out; check_template reports them."""
    t = template_for(contest.script)
    labelled = contest.script.labelled()
    side_to_id = {label: sid for sid, label in t.sides.items()}
    first, second = side_order(contest.id)
    order = []
    placed_sides = False
    for sid in t.sections:
        if sid in t.sides:
            if placed_sides:
                continue
            placed_sides = True
            want = [side_to_id[first], side_to_id[second]]
        else:
            want = [sid]
        for w in want:
            order += [(label, sec) for label, sec in labelled if sec.id == w]
    return tuple(order)


def section_order(contest: Contest) -> tuple[str, ...]:
    """Section labels (Script.labels) in narration/playback order; see
    playback_sections."""
    return tuple(label for label, _ in playback_sections(contest))


def narration_lines(contest: Contest) -> tuple[NarrationLine, ...]:
    """Every script line, in playback order."""
    return tuple(NarrationLine(label, i, line.text)
                 for label, sec in playback_sections(contest)
                 for i, line in enumerate(sec.lines))


def narration_text(contest: Contest) -> str:
    """The text `python -m ballotreels narration` writes to narration.txt:
    each line's text, one per line, in playback order."""
    return "".join(f"{line.text}\n" for line in narration_lines(contest))


def _load_phrases(contest: Contest) -> list[dict] | None:
    path = contest.path / "narration.json"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc["phrases"]


def match_phrases(contest: Contest) -> tuple[NarrationSpan, ...] | None:
    """Each script line's (start, end) span on the narration audio's clock,
    or None when there are no narration sidecars to read.

    Maps the sidecar's phrases back to script lines by re-splitting each
    line's text the way `say` does (`videobuilder.speech.phrases`) and
    consuming that many phrases off the sidecar's list; raises NarrationError
    the moment a phrase's text doesn't match, since that means the sidecars
    are stale for the current script and must be regenerated.
    """
    phrases = _load_phrases(contest)
    if phrases is None:
        return None
    from videobuilder import speech  # only this function needs videobuilder

    where = contest.path / "narration.json"
    spans = []
    pos = 0
    for line in narration_lines(contest):
        expected = speech.phrases(line.text)
        n = len(expected)
        chunk = phrases[pos:pos + n]
        got = [p["text"] for p in chunk]
        if got != expected:
            raise NarrationError(
                f"{where}: phrase(s) at index {pos} are {got!r}, expected "
                f"{expected!r} from {line.section}.line[{line.index}]; "
                f"regenerate the narration for the current script")
        spans.append(NarrationSpan(line.section, line.index,
                                    chunk[0]["start"], chunk[-1]["end"]))
        pos += n
    if pos != len(phrases):
        raise NarrationError(
            f"{where}: has {len(phrases)} phrases, but the script's lines "
            f"account for only {pos}; regenerate the narration for the "
            f"current script")
    return tuple(spans)


MISSING, STALE, CURRENT = "missing", "stale", "current"


def narration_state(contest: Contest) -> str:
    """Whether the contest's committed narration is MISSING (no
    narration.json, or one that records no take with no narration.wav
    beside it), STALE (its phrases no longer match the script's lines) or
    CURRENT (narrated from exactly this script's text). A current
    narration has passed `say`'s transcript check, so it is reused as it
    is; the pre-narration checks (speakability, spoken length, side basis)
    apply only to a script that is not.

    A narration.json that records its take (narration_store) is narrated
    whether or not the audio is here: narration_store.materialize puts it
    in place wherever a stage plays it. One recorded before takes were
    (`narration record` reports it) still counts while its narration.wav
    sits beside it."""
    from .narration_store import recorded_take
    path = contest.path
    if not (path / "narration.json").is_file():
        return MISSING
    if (recorded_take(path) is None
            and not (path / "narration.wav").is_file()):
        return MISSING
    try:
        match_phrases(contest)
    except NarrationError:
        return STALE
    except (KeyError, ValueError, TypeError):
        return STALE  # an unreadable sidecar, or a template check_template reports
    except ImportError:
        # No videobuilder to split lines the way `say` does: compare the
        # whole text instead, which `say`'s splitting never changes.
        doc = json.loads((path / "narration.json").read_text(encoding="utf-8"))
        said = " ".join(p["text"] for p in doc.get("phrases", ()))
        script = " ".join(" ".join(ln.text.split())
                          for ln in narration_lines(contest))
        return CURRENT if said == script else STALE
    return CURRENT


def unreused_phrases(contest: Contest) -> tuple[NarrationLine, ...] | None:
    """The phrases `say` would synthesise afresh when re-narrating the
    current script, each as a NarrationLine whose `text` is the phrase
    (not the whole line): every phrase when there is no narration.wav or
    no narration.json `phrase_cache` to reuse from, otherwise each phrase
    whose cache key no committed phrase has. A Gemini phrase's key is its
    own text plus the previous phrase's as context (videobuilder.speech
    `_gemini_style`), so an edited line's phrases and the phrase right
    after them are synthesised again, and nothing else is. Assumes the
    narrating host's TTS settings are the ones the sidecar recorded.
    Without videobuilder to split lines the way `say` does, every line is
    returned whole; None, meaning every line, for a script whose template
    is unknown (check_template reports it)."""
    try:
        lines = narration_lines(contest)
    except KeyError:
        return None
    path = contest.path
    cache = []
    if (path / "narration.wav").is_file() and (path / "narration.json").is_file():
        try:
            doc = json.loads((path / "narration.json").read_text(encoding="utf-8"))
            cache = [e["key"]["text"] for e in doc.get("phrase_cache") or ()]
        except (ValueError, KeyError, TypeError):
            cache = []
    try:
        from videobuilder import speech
    except ImportError:
        return lines
    committed = set(zip([None, *cache], cache))
    out, previous = [], None
    for line in lines:
        for text in speech.phrases(line.text):
            if (previous, text) not in committed:
                out.append(NarrationLine(line.section, line.index, text))
            previous = text
    return tuple(out)


def side_durations(contest: Contest
                   ) -> tuple[tuple[str, float], tuple[str, float]] | None:
    """Each side section's spoken duration in seconds (the span from its
    first word to its last, across all its lines), or None when there are
    no sidecars, or the script isn't a two-sided measure."""
    spans = match_phrases(contest)
    if spans is None:
        return None
    side_ids = [label for label, s in contest.script.labelled()
                if s.side is not None]
    if len(side_ids) != 2:
        return None
    bounds: dict[str, list[float]] = {}
    for span in spans:
        if span.section not in side_ids:
            continue
        b = bounds.setdefault(span.section, [span.start, span.end])
        b[0], b[1] = min(b[0], span.start), max(b[1], span.end)
    return tuple((sid, bounds[sid][1] - bounds[sid][0]) for sid in side_ids)


# More than this is a real imbalance in the script (STANDARD.md rule 2.2),
# not TTS noise; check_airtime fails rather than padding past it.
SIDE_PAD_CAP = 2.0


@dataclass(frozen=True)
class SidePad:
    """The silence narration.padded_spans adds to make the two side
    sections last exactly as long on screen (STANDARD.md rule 2.2): `side`
    is the shorter one, whose last word falls at `at` seconds into the
    narration; `seconds` of silence goes there, pushing everything after
    it later by that much."""
    side: str
    at: float
    seconds: float


def side_pad(contest: Contest, fps: int = 30) -> SidePad | None:
    """The pad that makes the two side sections last exactly the same
    number of frames on screen, or None when there are no sidecars, the
    script isn't two-sided, or the two already match to the frame. Does
    not enforce SIDE_PAD_CAP: check_airtime does, since this is used by the
    renderer too, which must still lay out *something* for an over-cap
    script.

    The pad is a whole number of frames, sized from the unpadded layout's
    own two section lengths (storyboard.side_frames) rather than from the
    spoken durations in seconds, so that the padded section boundaries,
    each rounded to a frame on its own, still come out equal: the side
    with fewer frames is padded by the difference. That is re-measured
    with the pad in place, a few times at most, for the rare boundary that
    does not move by exactly the pad (a page lead pinned to the previous
    section's last word, or a float landing on a half frame)."""
    from .storyboard import side_frames  # storyboard imports this module

    if side_durations(contest) is None:
        return None
    frames = side_frames(contest, None, fps)
    if frames is None:
        return None
    (side_a, fa), (side_b, fb) = frames
    if fa == fb:
        return None
    short = side_a if fa < fb else side_b
    at = max(s.end for s in match_phrases(contest) if s.section == short)
    k = abs(fa - fb)
    for _ in range(4):
        pad = SidePad(short, at, k / fps)
        got = dict(side_frames(contest, pad, fps))
        diff = got[side_b if short == side_a else side_a] - got[short]
        if diff == 0 or k + diff <= 0:
            break
        k += diff
    return pad


def _shift(t: float, pad: SidePad | None) -> float:
    """`t`, moved later by `pad`'s silence if `t` falls after the pad."""
    return t if pad is None or t <= pad.at else t + pad.seconds


def padded_spans(contest: Contest, fps: int = 30,
                 pad: SidePad | None | bool = True
                 ) -> tuple[NarrationSpan, ...] | None:
    """match_phrases's spans with the side pad (side_pad) folded in: every
    span after the pad point moved later by its length, so the picture
    (and anything else on the narration's clock) follows the padded audio
    actually played, not the original narration file's. `pad` is the pad
    to fold in, or True (the default) for side_pad's own."""
    spans = match_phrases(contest)
    if spans is None:
        return None
    if pad is True:
        pad = side_pad(contest, fps)
    if pad is None:
        return spans
    return tuple(NarrationSpan(s.section, s.index, _shift(s.start, pad),
                               _shift(s.end, pad))
                for s in spans)


def shift_track(track, pad: SidePad | None):
    """A `videobuilder.captions.Track` with every word after the side
    pad's point moved later by its length, the same way padded_spans
    shifts script-line spans. `track` back unchanged when `pad` is None."""
    if pad is None:
        return track
    from dataclasses import replace
    return type(track)(replace(w, start=_shift(w.start, pad),
                               end=_shift(w.end, pad))
                       for w in track)


def padded_phrases(phrases, pad: SidePad | None):
    """`videobuilder.speech.Narration.phrases` shifted by the side pad, the
    same way padded_spans shifts script-line spans."""
    if pad is None:
        return phrases
    from dataclasses import replace
    return tuple(replace(p, start=_shift(p.start, pad), end=_shift(p.end, pad))
                for p in phrases)
