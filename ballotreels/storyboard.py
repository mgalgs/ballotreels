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
- The closing sources card follows the narration, for as long as it takes
  to read (1 s plus its words at 3 words a second), listing every source
  the script cites (rule 1.5).
"""

from __future__ import annotations

from dataclasses import dataclass

from .contest import Contest, Line, Section, Source, Visual
from .narration import NarrationError, match_phrases, playback_sections

FPS = 30
END_HOLD = 0.5  # s held on the last line before the sources card
PAGE_LEAD = 0.25  # s before a section's first word that its page starts
READ_WPS = 3.0  # words a second, the read-time floor


def frame(seconds: float, fps: int = FPS) -> int:
    """Seconds to the nearest frame, halves rounding up (never banker's)."""
    return int(seconds * fps + 0.5)


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
    source: Source | None  # None for a `words` visual: its line cites
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


def cited_sources(contest: Contest) -> tuple[Source, ...]:
    """Every source a line or chart cites, in sources.toml order."""
    ids = set()
    for sec in contest.script.sections:
        for line in sec.lines:
            ids.update(line.sources or ())
            if line.visual is not None and isinstance(line.visual.source, str):
                ids.add(line.visual.source)
    return tuple(s for s in contest.sources if s.id in ids)


def sources_card_seconds(sources: tuple[Source, ...]) -> float:
    """Read time for the sources card: its heading and each publisher."""
    words = 1 + sum(len(s.publisher.split()) for s in sources)
    return 1 + words / READ_WPS


def layout(contest: Contest, seconds: float, fps: int = FPS) -> Storyboard:
    """Lay the contest out on the narration's clock; `seconds` is the
    narration audio's length. Raises NarrationError when the contest has no
    narration sidecars, or they don't match the script."""
    spans = match_phrases(contest)
    if spans is None:
        raise NarrationError(
            f"{contest.path}: no narration sidecars; run `python -m "
            f"ballotreels narration` then `videobuilder say` first")
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
    end = narration_end + frame(sources_card_seconds(cited), fps)
    return Storyboard(fps, tuple(sections), narration_end, end, cited)


__all__ = ["ChartBeat", "LineBeat", "NarrationError", "SectionBeat",
           "Storyboard", "cited_sources", "frame", "layout",
           "sources_card_seconds"]
