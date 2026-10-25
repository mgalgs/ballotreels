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
from .standard import TEMPLATES, side_order


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
    t = TEMPLATES[contest.script.template][contest.script.template_version]
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
