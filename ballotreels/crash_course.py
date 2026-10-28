"""A state's crash course: one video through every statewide measure on
its ballot (docs/ARCHITECTURE.md, "The crash course").

Nothing in it is written for it. Each measure gets one slot, and the
slot replays two sections of that measure's own film, picture and
committed narration alike: its opening section (what the measure is)
and its vote section (what a yes and a no vote would do), or, for a
choice question (STANDARD.md section 8), its `choices` section, which
names the options. The audio is cut from the measure's committed
narration.wav by its narration.json phrase timings; the TTS is never
asked for anything. Each slot is as long as its own member's two
sections plus SLOT_GAP_SECONDS, for which it holds its last frame in
silence; a slot is never padded out to match a longer one, so the
course is the sum of its slots.

The film around the slots says nothing either: a short opening card
with the state's name, how many statewide measures it has and the
election's date, and a closing sources card listing what the reused
lines cite, grouped by measure.

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
from .narration import (CURRENT, MISSING, NarrationError, match_phrases,
                        narration_state, padded_spans, playback_sections)
from .standard import CHOICES
from .storyboard import FPS, Storyboard, frame, layout

# The crash course's own template version, in its cache key: bump it when
# its film changes what it draws (docs/ARCHITECTURE.md).
TEMPLATE_VERSION = 2

# Fewer statewide measures than this, and a state has no crash course:
# one measure's own video already is one.
MIN_MEMBERS = 2

OPENING_SECONDS = 2.0   # the opening card, on screen only
SLOT_GAP_SECONDS = 0.5  # added to each member's own two sections
AUDIO_MARGIN = 0.1      # s of the narration kept either side of a part's words
AUDIO_FADE = 3          # frames each cut of the narration fades over

OPENING = "what"
VOTE = "vote"

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
        for name in DIGEST_FILES:
            h.update(f"{name}={_file_digest(d / name)}\0".encode("utf-8"))
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
class Part:
    """One of the two sections a slot replays: frames [start, end) of the
    member's own film, and the narration under it."""
    label: str  # the section's label (Script.labels)
    heading: str
    lines: tuple[Line, ...]
    start: int  # frames, on the member film's clock
    end: int
    # the narration cut for it: seconds into narration.wav, and frames
    # into this part (from `start`) where it starts playing, for how long
    audio_from: float
    audio_at: int
    audio_frames: int
    # the reused words' span, seconds on the member film's (padded) clock,
    # for the captions
    said_from: float
    said_to: float

    @property
    def frames(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Member:
    entry: IndexEntry
    contest: Contest
    board: Storyboard
    parts: tuple[Part, Part]
    cited: tuple[Source, ...]  # what the reused lines cite, sources.toml order

    @property
    def frames(self) -> int:
        """The member's two sections, back to back, in frames."""
        return sum(p.frames for p in self.parts)

    @property
    def lines(self) -> tuple[Line, ...]:
        return tuple(ln for p in self.parts for ln in p.lines)


@dataclass(frozen=True)
class CrashCourse:
    entry: IndexEntry
    election: Election
    state_name: str  # as a sentence starts it: "the" capitalized
    date: str        # the election's, "November 3, 2026"
    members: tuple[Member, ...]
    fps: int
    opening: int  # the opening card's frames
    slots: tuple[int, ...]  # each member's slot's frames, in ballot order

    def slot_start(self, i: int) -> int:
        return self.opening + sum(self.slots[:i])

    @property
    def slots_end(self) -> int:
        """The frame the sources card starts."""
        return self.slot_start(len(self.members))

    @property
    def headline(self) -> str:
        n = len(self.members)
        return f"{n} statewide measure{'' if n == 1 else 's'}"


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


def vote_section(contest: Contest) -> str:
    """The id of the section a slot closes on: `vote`, what a yes and a no
    vote would do; or, for a choice question, `choices`, which names the
    options."""
    return CHOICES if contest.script.choices is not None else VOTE


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


def _part(contest: Contest, board: Storyboard, label: str, fps: int) -> Part:
    beat = next(s for s in board.sections if s.label == label)
    said = [s for s in match_phrases(contest) if s.section == label]
    padded = [s for s in padded_spans(contest, fps) if s.section == label]
    u0 = min(s.start for s in said)
    p0, p1 = (min(s.start for s in padded), max(s.end for s in padded))
    # The side pad falls inside a side section, never inside the opening
    # or the vote section, so the whole part sits one shift from the audio
    # file's own clock.
    shift = p0 - u0
    a = max(beat.start, frame(p0 - AUDIO_MARGIN, fps))
    b = min(beat.end, frame(p1 + AUDIO_MARGIN, fps))
    return Part(label=label, heading=beat.section.heading,
                lines=beat.section.lines, start=beat.start, end=beat.end,
                audio_from=max(0.0, a / fps - shift),
                audio_at=a - beat.start, audio_frames=b - a,
                said_from=p0, said_to=p1)


def _cited(contest: Contest, lines: tuple[Line, ...]) -> tuple[Source, ...]:
    ids = set()
    for line in lines:
        ids.update(line.sources or ())
        if line.visual is not None and isinstance(line.visual.source, str):
            ids.add(line.visual.source)
    return tuple(s for s in contest.sources if s.id in ids)


def member_layout(entry: IndexEntry, contest: Contest,
                  fps: int = FPS) -> Member:
    """The member's two parts, on its own film's clock."""
    doc = json.loads((contest.path / "narration.json").read_text(
        encoding="utf-8"))
    try:
        board = layout(contest, doc["seconds"], fps)
    except (NarrationError, KeyError) as e:
        raise CrashCourseError(f"{_who(entry)}: {e}") from None
    labels = [label for label, _ in playback_sections(contest)]
    want = vote_section(contest)
    votes = [label for label, sec in playback_sections(contest)
             if sec.id == want]
    if not labels or labels[0] != OPENING or len(votes) != 1:
        raise CrashCourseError(
            f"{_who(entry)}: needs one {OPENING!r} section first and one "
            f"{want!r} section to make its slot from")
    parts = (_part(contest, board, labels[0], fps),
             _part(contest, board, votes[0], fps))
    lines = parts[0].lines + parts[1].lines
    return Member(entry, contest, board, parts, _cited(contest, lines))


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
    return CrashCourse(
        entry=entry, election=index.election,
        state_name=_state_name(index.election.state),
        date=election_date(index.election.id),
        members=tuple(members), fps=fps,
        opening=frame(OPENING_SECONDS, fps),
        slots=tuple(m.frames + gap for m in members))


def chapters(course: CrashCourse) -> list[dict[str, object]]:
    """One chapter per measure, in ballot order: where its slot starts, in
    seconds (rounded up to the millisecond, as storyboard.chapters does),
    and its title as contests.toml gives it (its designation and short
    title). Neither the opening card nor the sources card is one."""
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
    measure's video publishes its script.toml: each member's reused
    sections and their lines, verbatim. Derived, never edited."""
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
        for p in m.parts:
            out += ["[[member.section]]", f"id = {q(p.label)}",
                    f"heading = {q(p.heading)}",
                    "lines = [" + ", ".join(q(ln.text) for ln in p.lines)
                    + "]", ""]
    return "\n".join(out)


def election_dir_for(repo: str | Path, election_id: str) -> Path:
    return Path(repo) / "data" / election_id


def is_election_dir(path: str | Path) -> bool:
    """Whether `path` is an election's directory (it has a contests.toml),
    which `render` and the runners take to mean its crash course."""
    return os.path.isfile(os.path.join(path, "contests.toml"))
