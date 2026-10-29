"""A state's crash course: one video through every statewide measure on
its ballot (docs/ARCHITECTURE.md, "The crash course").

Nothing in it is written for it. The measures are tiles on pages, a
contact sheet of up to PAGE_TILES a page, split as evenly as they go
over the fewest pages (page_sizes), in ballot order. Each tile says one
line of its measure's own script, verbatim: the first line of its
`change` section (what the measure would do), or, in a script with
none, of its opening section. The audio is that line's cut of the
measure's committed narration.wav, by its narration.json phrase
timings; the TTS is never asked for anything. Each tile's slot is as
long as its line plus SLOT_GAP_SECONDS, and a slot is never padded out
to match a longer one, so a page is its heading's lead plus its slots.

The film around the pages says nothing either: a short opening card
with the state's name, how many statewide measures it has and the
election's date; a still closing page pointing to each measure's own
video; and a sources card listing what the reused lines cite, grouped
by measure.

This module lays all of that out as frames and seconds, with no drawing
(film/crash_course.py draws it), the same way ballotreels.storyboard does
for a measure's own film.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from .contest import Contest, ContestError, Line, Source, load_contest
from .index import (CRASH_COURSE, ContestIndex, Election, IndexEntry,
                    load_index)
from .narration_store import recorded_take
from .narration import (CURRENT, MISSING, NarrationError, match_phrases,
                        narration_state, playback_sections)
from .storyboard import FPS, frame

# The crash course's own template version, in its cache key: bump it when
# its film changes what it draws (docs/ARCHITECTURE.md).
TEMPLATE_VERSION = 3

# Fewer statewide measures than this, and a state has no crash course:
# one measure's own video already is one.
MIN_MEMBERS = 2

OPENING_SECONDS = 2.0    # the opening card, on screen only
PAGE_LEAD_SECONDS = 1.0  # a page's heading, before its first tile
SLOT_GAP_SECONDS = 0.5   # added to each tile's own one-liner
CLOSING_SECONDS = 3.0    # the closing page, still and silent
AUDIO_MARGIN = 0.1       # s of the narration kept either side of a line's words
AUDIO_FADE = 3           # frames each cut of the narration fades over
PAGE_TILES = 6           # tiles on a page, at most

OPENING = "what"
CHANGE = "change"

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


class CrashCourseError(Exception):
    """A crash course that can't be made from the committed data; the
    message names the measure at fault."""


# ---- identity: the contest index's entry, and its cache key ----

def crash_course_id(election_id: str) -> str:
    return f"{election_id}-{CRASH_COURSE}"


def member_entries(election: Election,
                   entries: tuple[IndexEntry, ...]) -> tuple[IndexEntry, ...]:
    """The statewide measures, in contests.toml's order (the ballot's)."""
    return tuple(e for e in entries
                 if e.kind == "measure" and e.division == election.state)


def crash_course_entry(election: Election, entries: tuple[IndexEntry, ...],
                       election_dir: str | Path) -> IndexEntry | None:
    """The index entry of the election's crash course, or None when it has
    fewer than MIN_MEMBERS statewide measures."""
    members = member_entries(election, entries)
    if len(members) < MIN_MEMBERS:
        return None
    return IndexEntry(
        id=crash_course_id(election.id),
        kind=CRASH_COURSE,
        division=election.state,
        title=f"{election.title}: {len(members)} statewide measures",
        members=tuple(e.id for e in members),
        election_dir=str(election_dir),
    )


# What a member's slot is cut from, and so what the crash course's key
# hashes: a change to any of these is a different crash course.
DIGEST_FILES = ("script.toml", "sources.toml", "narration.json",
                "narration.wav")

_file_digests: dict[tuple[str, int, int], str] = {}


def _file_digest(path: Path) -> str:
    """SHA-256 of the file at `path`, or "-" when there is none; kept per
    (path, size, mtime), so a page view does not re-read every member's
    narration audio."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return "-"
    memo = (str(path), st.st_size, st.st_mtime_ns)
    if memo not in _file_digests:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _file_digests[memo] = h.hexdigest()
    return _file_digests[memo]


def member_dir(election_dir: str | Path, election_id: str,
               contest_id: str) -> Path:
    return Path(election_dir) / contest_id[len(election_id) + 1:]


def digest(entry: IndexEntry) -> str:
    """16 hex characters over every member's id and every file its slot
    is cut from (DIGEST_FILES), in ballot order."""
    election_id = entry.id[:-len(CRASH_COURSE) - 1]
    h = hashlib.sha256()
    for cid in entry.members:
        d = member_dir(entry.election_dir, election_id, cid)
        h.update(cid.encode("utf-8") + b"\0")
        take = recorded_take(d)
        for name in DIGEST_FILES:
            # The take narration.json records is narration.wav's SHA-256:
            # the same digest, whether or not the audio is here.
            value = (take.sha256 if name == "narration.wav" and take
                     else _file_digest(d / name))
            h.update(f"{name}={value}\0".encode("utf-8"))
    return h.hexdigest()[:16]


def key_contest(entry: IndexEntry) -> str:
    """The contest part of the crash course's cache key: its id and its
    members' digest, `<id>@<digest>`."""
    return f"{entry.id}@{digest(entry)}"


def split_key_contest(contest: str) -> tuple[str, str | None]:
    """(contest id, digest) from a cache key's contest part: the digest is
    None for any contest but a crash course."""
    cid, at, dig = contest.partition("@")
    if at and cid.endswith(f"-{CRASH_COURSE}"):
        return cid, dig
    return contest, None


def is_crash_course(contest: str) -> bool:
    """Whether a cache key's contest part (or a contest id) is a crash
    course's."""
    return split_key_contest(contest)[0].endswith(f"-{CRASH_COURSE}")


# ---- the layout ----

@dataclass(frozen=True)
class Member:
    """One measure's tile: the line it says (its one-liner, verbatim) and
    the cut of its committed narration that says it."""
    entry: IndexEntry
    contest: Contest
    section: str  # the label (Script.labels) of the section the line opens
    line: Line
    # the narration cut for it: seconds into narration.wav, for how long
    audio_from: float
    audio_frames: int
    cited: tuple[Source, ...]  # what the line cites, sources.toml order

    @property
    def frames(self) -> int:
        """The tile's own content: its one-liner, said."""
        return self.audio_frames

    @property
    def lines(self) -> tuple[Line, ...]:
        return (self.line,)

    @property
    def fallback(self) -> bool:
        """Whether the script has no CHANGE section, so the tile says its
        opening line instead."""
        return all(sec.id != CHANGE for sec in self.contest.script.sections)


@dataclass(frozen=True)
class CrashCourse:
    entry: IndexEntry
    election: Election
    state_name: str  # as a sentence starts it: "the" capitalized
    date: str        # the election's, "November 3, 2026"
    members: tuple[Member, ...]
    fps: int
    opening: int  # the opening card's frames
    lead: int     # each page's frames before its first tile, for its heading
    pages: tuple[tuple[int, ...], ...]  # each page's members, by index
    slots: tuple[int, ...]  # each member's slot's frames, in ballot order
    closing: int  # the closing page's frames, before the sources pages

    def page_start(self, k: int) -> int:
        """The frame page k comes on; for k past the last page, the frame
        the closing page does."""
        return (self.opening + self.lead * k
                + sum(self.slots[i] for p in self.pages[:k] for i in p))

    def page_of(self, i: int) -> int:
        return next(k for k, p in enumerate(self.pages) if i in p)

    def slot_start(self, i: int) -> int:
        k = self.page_of(i)
        return (self.page_start(k) + self.lead
                + sum(self.slots[j] for j in self.pages[k] if j < i))

    @property
    def slots_end(self) -> int:
        """The frame the closing page starts."""
        return self.page_start(len(self.pages))

    @property
    def sources_start(self) -> int:
        """The frame the sources pages start."""
        return self.slots_end + self.closing

    @property
    def headline(self) -> str:
        n = len(self.members)
        return f"{n} statewide measure{'' if n == 1 else 's'}"


def page_sizes(n: int, most: int = PAGE_TILES) -> tuple[int, ...]:
    """How many tiles each page has: n split as evenly as it goes over the
    fewest pages of at most `most`, the larger pages first (14: 5, 5, 4)."""
    k = -(-n // most)
    base, extra = divmod(n, k)
    return (base + 1,) * extra + (base,) * (k - extra)


def election_date(election_id: str) -> str:
    """"November 3, 2026" from an id ending in its date, 2026-11-03."""
    y, m, d = election_id[-10:].split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}, {y}"


def _state_name(division: str) -> str:
    from .ballots import state_of
    from .geo.states import STATE_NAMES
    abbr = state_of(division) or ""
    name = STATE_NAMES.get(abbr, abbr.upper())
    return name[0].upper() + name[1:]


def _who(entry: IndexEntry) -> str:
    return f"{entry.title} ({entry.id})"


def load_member(entry: IndexEntry, election_dir: str | Path,
                election_id: str) -> Contest:
    """The member's contest, with a committed narration of exactly its
    current script, or CrashCourseError naming it: the same rule the
    worker holds a single measure to, except that a missing narration is
    not made here either, since a crash course never asks the TTS."""
    path = member_dir(election_dir, election_id, entry.id)
    try:
        contest = load_contest(path)
    except ContestError as e:
        raise CrashCourseError(f"{_who(entry)}: {e}") from None
    state = narration_state(contest)
    if state == MISSING:
        raise CrashCourseError(
            f"{_who(entry)}: has no committed narration (narration.json and "
            f"narration.wav); narrate it on the host with scripts/narrate.sh "
            f"and commit the sidecars first")
    if state != CURRENT:
        raise CrashCourseError(
            f"{_who(entry)}: the committed narration (narration.json) no "
            f"longer matches its script; re-narrate it on the host with "
            f"scripts/narrate.sh and commit the sidecars")
    return contest


def _cited(contest: Contest, lines: tuple[Line, ...]) -> tuple[Source, ...]:
    ids = set()
    for line in lines:
        ids.update(line.sources or ())
        if line.visual is not None and isinstance(line.visual.source, str):
            ids.add(line.visual.source)
    return tuple(s for s in contest.sources if s.id in ids)


def member_layout(entry: IndexEntry, contest: Contest,
                  fps: int = FPS) -> Member:
    """The member's one-liner and its cut of the narration: the first line
    of its CHANGE section (what the measure would do), or, in a script
    with none, of its OPENING section."""
    doc = json.loads((contest.path / "narration.json").read_text(
        encoding="utf-8"))
    sections = playback_sections(contest)
    label = next((lb for lb, sec in sections if sec.id == CHANGE), None)
    if label is None and sections and sections[0][1].id == OPENING:
        label = sections[0][0]
    sec = dict(sections).get(label)
    if sec is None or not sec.lines:
        raise CrashCourseError(
            f"{_who(entry)}: needs a {CHANGE!r} or an {OPENING!r} section "
            f"with a line to make its tile from")
    try:
        spans = list(match_phrases(contest))
    except NarrationError as e:
        raise CrashCourseError(f"{_who(entry)}: {e}") from None
    k = next(j for j, s in enumerate(spans)
             if s.section == label and s.index == 0)
    said = spans[k]
    # AUDIO_MARGIN either side of the words, but never past halfway to
    # the phrase before or after, so not a breath of another line plays
    lo = (spans[k - 1].end + said.start) / 2 if k else 0.0
    hi = ((said.end + spans[k + 1].start) / 2 if k + 1 < len(spans)
          else doc.get("seconds", said.end + AUDIO_MARGIN))
    a = max(lo, said.start - AUDIO_MARGIN)
    b = min(hi, said.end + AUDIO_MARGIN)
    line = sec.lines[0]
    return Member(entry, contest, label, line, audio_from=a,
                  audio_frames=max(1, frame(b - a, fps)),
                  cited=_cited(contest, (line,)))


def plan(election_dir: str | Path, fps: int = FPS,
         index: ContestIndex | None = None) -> CrashCourse:
    """The crash course of the election in `election_dir`, laid out from
    its committed data alone, or CrashCourseError."""
    election_dir = Path(election_dir)
    if index is None:
        index = load_index(election_dir)
    entry = index.crash_course
    if entry is None:
        raise CrashCourseError(
            f"{index.election.id}: fewer than {MIN_MEMBERS} statewide "
            f"measures, so no crash course")
    members = []
    for cid in entry.members:
        m = index.get(cid)
        contest = load_member(m, election_dir, index.election.id)
        members.append(member_layout(m, contest, fps))
    gap = frame(SLOT_GAP_SECONDS, fps)
    pages, i = [], 0
    for n in page_sizes(len(members)):
        pages.append(tuple(range(i, i + n)))
        i += n
    return CrashCourse(
        entry=entry, election=index.election,
        state_name=_state_name(index.election.state),
        date=election_date(index.election.id),
        members=tuple(members), fps=fps,
        opening=frame(OPENING_SECONDS, fps),
        lead=frame(PAGE_LEAD_SECONDS, fps),
        pages=tuple(pages),
        slots=tuple(m.frames + gap for m in members),
        closing=frame(CLOSING_SECONDS, fps))


def chapters(course: CrashCourse) -> list[dict[str, object]]:
    """One chapter per measure, in ballot order: where its slot starts, in
    seconds (rounded up to the millisecond, as storyboard.chapters does),
    and its title as contests.toml gives it (its designation and short
    title). Neither the opening card, a page's heading, the closing page
    nor the sources card is one."""
    return [{"start": math.ceil(course.slot_start(i) * 1000 / course.fps
                                - 1e-6) / 1000,
             "title": m.entry.title}
            for i, m in enumerate(course.members)]


def sources(course: CrashCourse) -> list[dict[str, object]]:
    """Every source the reused lines cite, grouped by measure in ballot
    order, each naming the measure it is cited for (a source two measures
    cite is listed under each)."""
    return [{"contest": m.entry.id, "id": s.id, "kind": s.kind,
             "publisher": s.publisher, "url": s.url,
             "retrieved": s.retrieved, "credit": s.credit}
            for m in course.members for s in m.cited]


def script_toml(course: CrashCourse) -> str:
    """A record of what the crash course says, in TOML, published where a
    measure's video publishes its script.toml: each member's one-liner,
    verbatim, under the section it opens. Derived, never edited."""
    def q(s: str) -> str:
        return json.dumps(s, ensure_ascii=False)

    out = [f"# Derived by ballotreels.crash_course from each member's "
           f"committed script\n# and narration; nothing here is written "
           f"by hand.\n",
           f"contest = {q(course.entry.id)}",
           f"template = {q(CRASH_COURSE)}",
           f"template_version = {TEMPLATE_VERSION}",
           f"digest = {q(digest(course.entry))}", ""]
    for m in course.members:
        out += ["[[member]]", f"contest = {q(m.entry.id)}",
                f"title = {q(m.entry.title)}", ""]
        sec = dict(playback_sections(m.contest))[m.section]
        out += ["[[member.section]]", f"id = {q(m.section)}",
                f"heading = {q(sec.heading)}",
                "lines = [" + ", ".join(q(ln.text) for ln in m.lines)
                + "]", ""]
    return "\n".join(out)


def election_dir_for(repo: str | Path, election_id: str) -> Path:
    return Path(repo) / "data" / election_id


def is_election_dir(path: str | Path) -> bool:
    """Whether `path` is an election's directory (it has a contests.toml),
    which `render` and the runners take to mean its crash course."""
    return os.path.isfile(os.path.join(path, "contests.toml"))
