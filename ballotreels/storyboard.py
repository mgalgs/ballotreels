"""The measure film's timeline, laid out from the narration.

Everything here is frame arithmetic, with no drawing and no videobuilder:
the film template (film/measure.py) draws what this lays out. Times come
from the committed narration's phrases (`match_phrases`), in playback
order (`playback_sections`), so the picture follows the voice:

- A section's page starts in the pause before its first word (so the old
  page can be rubbed out while nobody is speaking) and runs until the next
  section's page starts. The first section starts on frame 0.
- A line runs from its first word until the next line's first word (the
  first line of a section from the section's start; the last line of the
  film until the narration's end plus a short hold).
- A visual appears with its line and stays up through the lines after it
  in its section, until a later line brings its own visual or the section
  ends (docs/SCRIPT-FORMAT.md). Its source line, if it has one, is on
  screen for exactly that span (STANDARD.md rule 7.1).
- The closing sources card follows the narration for SOURCES_CARD_SECONDS,
  listing every source the script cites (rule 1.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .contest import Contest, Line, Section, Source, Visual
from .narration import (NarrationError, SidePad, padded_spans,
                        playback_sections, side_pad)

FPS = 30
END_HOLD = 0.5  # s held on the last line before the sources card
PAGE_LEAD = 0.25  # s before a section's first word that its page starts
SOURCES_CARD_SECONDS = 5.0  # the sources stay listed on the video's page


def frame(seconds: float, fps: int = FPS) -> int:
    """Seconds to the nearest frame, halves rounding up (never banker's).
    The product is first rounded to a millionth of a frame, so float noise
    can't tip an exact half either way: 63.15 s is 1894.5 frames, but
    63.15 + 1.0 multiplies out to 1924.4999..., and a time shifted by a
    whole-frame pad (narration.side_pad) must still land exactly that many
    frames later."""
    return int(round(seconds * fps, 6) + 0.5)


@dataclass(frozen=True)
class LineBeat:
    section: str  # the section's label (Script.labels)
    index: int  # 0-based index into that section's lines
    line: Line
    start: int  # frames
    end: int


@dataclass(frozen=True)
class ChartBeat:
    section: str
    index: int  # the line that carries it
    visual: Visual
    source: Source | None  # None for an illustration: its line cites
    start: int
    end: int


@dataclass(frozen=True)
class SectionBeat:
    label: str
    section: Section
    number: int  # 0-based position in playback order
    start: int
    end: int
    lines: tuple[LineBeat, ...]
    charts: tuple[ChartBeat, ...]


@dataclass(frozen=True)
class Storyboard:
    fps: int
    sections: tuple[SectionBeat, ...]
    narration_end: int  # frame the sources card starts
    end: int  # the film's length in frames
    cited: tuple[Source, ...]  # every cited source, in sources.toml order

    @property
    def lines(self) -> tuple[LineBeat, ...]:
        return tuple(b for s in self.sections for b in s.lines)

    @property
    def charts(self) -> tuple[ChartBeat, ...]:
        return tuple(c for s in self.sections for c in s.charts)

    def section_at(self, n: int) -> SectionBeat | None:
        """The section on screen at frame `n`, or None on the sources card."""
        for s in self.sections:
            if s.start <= n < s.end:
                return s
        return None


def chapters(board: Storyboard) -> list[dict[str, object]]:
    """One chapter per section, in playback order: where its page starts,
    in seconds, and its heading as the film writes it. The video's page
    lists them, to jump to a section; the sources card is not one. A start
    is rounded up to the millisecond, so seeking to it never lands on the
    previous section's last frame."""
    return [{"start": math.ceil(s.start * 1000 / board.fps - 1e-6) / 1000,
             "title": s.section.heading} for s in board.sections]


def cited_sources(contest: Contest) -> tuple[Source, ...]:
    """Every source a line or chart cites, in sources.toml order."""
    ids = set()
    for sec in contest.script.sections:
        for line in sec.lines:
            ids.update(line.sources or ())
            if line.visual is not None and isinstance(line.visual.source, str):
                ids.add(line.visual.source)
    return tuple(s for s in contest.sources if s.id in ids)


def layout(contest: Contest, seconds: float, fps: int = FPS) -> Storyboard:
    """Lay the contest out on the narration's clock; `seconds` is the
    narration audio's length (before any side pad: this adds the pad's own
    length, so the sources card follows the padded audio actually played).
    Raises NarrationError when the contest has no narration sidecars, or
    they don't match the script.

    The two side sections are padded to equal on-screen time (STANDARD.md
    rule 2.2, narration.side_pad): every line after the shorter side's last
    word is laid out `pad.seconds` later, same as the padded audio itself
    (film/measure.py builds that audio from the same side_pad)."""
    return _layout(contest, seconds, fps, side_pad(contest, fps))


def side_frames(contest: Contest, pad: SidePad | None, fps: int = FPS
                ) -> tuple[tuple[str, int], tuple[str, int]] | None:
    """Each side section's length in frames, in playback order, laid out
    with `pad` (None: unpadded), or None if the script isn't two-sided.
    narration.side_pad sizes its pad from this."""
    board = _layout(contest, 0.0, fps, pad)
    sides = tuple((sb.label, sb.end - sb.start) for sb in board.sections
                  if sb.section.side is not None)
    return sides if len(sides) == 2 else None


def _layout(contest: Contest, seconds: float, fps: int,
            pad: SidePad | None) -> Storyboard:
    spans = padded_spans(contest, fps, pad)
    if spans is None:
        raise NarrationError(
            f"{contest.path}: no narration sidecars; run `python -m "
            f"ballotreels narration` then `videobuilder say` first")
    if pad is not None:
        seconds += pad.seconds
    by_line = {(s.section, s.index): s for s in spans}
    order = playback_sections(contest)
    narration_end = frame(seconds, fps) + frame(END_HOLD, fps)

    # Each section's page: from the pause before its first word.
    starts = []
    prev_end = None
    for label, sec in order:
        first = by_line[(label, 0)].start
        if prev_end is None:
            starts.append(0)
        else:
            lead = max(prev_end, first - PAGE_LEAD)
            starts.append(min(frame(lead, fps), frame(first, fps)))
        prev_end = by_line[(label, len(sec.lines) - 1)].end
    ends = starts[1:] + [narration_end]

    sections = []
    for number, ((label, sec), s0, s1) in enumerate(zip(order, starts, ends)):
        line_starts = [s0] + [frame(by_line[(label, i)].start, fps)
                              for i in range(1, len(sec.lines))]
        line_ends = line_starts[1:] + [s1]
        lines = tuple(LineBeat(label, i, line, a, b) for i, (line, a, b)
                      in enumerate(zip(sec.lines, line_starts, line_ends)))
        with_charts = [b for b in lines if b.line.visual is not None]
        charts = []
        for k, b in enumerate(with_charts):
            until = with_charts[k + 1].start if k + 1 < len(with_charts) else s1
            sid = b.line.visual.source
            src = None if sid is None else contest.source(sid)
            if sid is not None and src is None:
                raise NarrationError(
                    f"{label}.line[{b.index}]: chart cites unknown source "
                    f"{b.line.visual.source!r}")
            charts.append(ChartBeat(label, b.index, b.line.visual, src,
                                    b.start, until))
        sections.append(SectionBeat(label, sec, number, s0, s1, lines,
                                    tuple(charts)))

    cited = cited_sources(contest)
    end = narration_end + frame(SOURCES_CARD_SECONDS, fps)
    return Storyboard(fps, tuple(sections), narration_end, end, cited)


__all__ = ["SOURCES_CARD_SECONDS", "ChartBeat", "LineBeat", "NarrationError",
           "SectionBeat", "Storyboard", "cited_sources", "frame", "layout",
           "side_frames"]
