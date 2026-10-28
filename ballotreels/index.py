"""Per-election contest index: data/<election>/contests.toml.

The index lists every contest on an election's ballot, whether or not
its sources or script exist yet (docs/ARCHITECTURE.md). The loader only
checks shape and the rules in this module's docstring; a contest that
fails to load at all (sources.toml missing or malformed) is a separate,
later concern (ballotreels.contest).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .standard import TEMPLATES

_MISSING = object()

KINDS = frozenset({"measure", "race"})

# A state's crash course (ballotreels.crash_course): an election-level
# contest of its own kind, derived from the statewide measures rather than
# listed in contests.toml, under this id suffix (and slug).
CRASH_COURSE = "crash-course"

# Division substrings, in ballot order (docs/ARCHITECTURE.md divisions are
# OCD-IDs; "state" is matched by equality with the election's own state
# division, the rest by substring).
LEVELS = ("state", "cd", "sldu", "sldl", "county")


class ContestIndexError(Exception):
    """A contests.toml that cannot be loaded, or an entry that breaks a
    rule of this index's format."""


@dataclass(frozen=True)
class Correction:
    date: str
    note: str


@dataclass(frozen=True)
class Election:
    id: str
    state: str
    title: str


@dataclass(frozen=True)
class IndexEntry:
    id: str
    kind: str
    division: str
    title: str
    number: str | None = None
    office: str | None = None
    corrections: tuple[Correction, ...] = ()
    # a choice question: its script has a [choices] table, so the page
    # speaks of its choices, not of two sides (docs/SCRIPT-FORMAT.md)
    choice: bool = False
    # a crash course: its members' contest ids, in ballot order, and the
    # election directory they are read from (its cache key hashes them)
    members: tuple[str, ...] = ()
    election_dir: str | None = field(default=None, compare=False,
                                     repr=False)


@dataclass(frozen=True)
class ContestIndex:
    election: Election
    entries: tuple[IndexEntry, ...]
    # the state's crash course, when it has statewide measures enough for
    # one (ballotreels.crash_course); never one of `entries`, so the
    # ballot, the state page's list and the sitemap are as they were
    crash_course: IndexEntry | None = None

    def get(self, contest_id: str) -> IndexEntry | None:
        for e in self.entries:
            if e.id == contest_id:
                return e
        if self.crash_course is not None and \
                self.crash_course.id == contest_id:
            return self.crash_course
        return None


def _get(table: dict[str, Any], key: str, typ: type, where: str,
         default: Any = _MISSING) -> Any:
    if key not in table:
        if default is _MISSING:
            raise ContestIndexError(f"{where}: missing key {key!r}")
        return default
    value = table[key]
    if not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
        raise ContestIndexError(
            f"{where}: {key!r} must be {typ.__name__}, "
            f"got {type(value).__name__}")
    return value


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise ContestIndexError(f"{path}: not found") from None
    except tomllib.TOMLDecodeError as e:
        raise ContestIndexError(f"{path}: {e}") from None


def _load_election(data: dict[str, Any], path: Path) -> Election:
    where = f"{path}: [election]"
    raw = _get(data, "election", dict, str(path))
    return Election(
        id=_get(raw, "id", str, where),
        state=_get(raw, "state", str, where),
        title=_get(raw, "title", str, where),
    )


def _load_corrections(raw: dict[str, Any], where: str) -> tuple[Correction, ...]:
    out = []
    for i, c in enumerate(_get(raw, "correction", list, where, [])):
        cwhere = f"{where} correction[{i}]"
        if not isinstance(c, dict):
            raise ContestIndexError(f"{cwhere}: must be a table")
        out.append(Correction(
            date=_get(c, "date", str, cwhere),
            note=_get(c, "note", str, cwhere),
        ))
    return tuple(out)


def _check_sources_match(entry: IndexEntry, election: Election,
                         contest_dir: Path, where: str) -> None:
    sources_path = contest_dir / "sources.toml"
    if not sources_path.is_file():
        return
    try:
        with sources_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        return  # ballotreels.contest will report the real error
    contest = data.get("contest")
    if not isinstance(contest, dict):
        return
    for key, expect in (("id", entry.id), ("election", election.id),
                        ("division", entry.division), ("kind", entry.kind)):
        got = contest.get(key)
        if got is not None and got != expect:
            raise ContestIndexError(
                f"{where}: sources.toml {key} {got!r} does not match "
                f"index {expect!r}")


def _is_choice_question(contest_dir: Path) -> bool:
    """Whether the script in `contest_dir` asks a choice question (has a
    [choices] table). False when there is no script, or it does not parse:
    ballotreels.contest reports that."""
    try:
        with (contest_dir / "script.toml").open("rb") as f:
            return isinstance(tomllib.load(f).get("choices"), dict)
    except (OSError, tomllib.TOMLDecodeError):
        return False


def _load_entry(raw: dict[str, Any], i: int, election: Election,
                election_dir: Path) -> IndexEntry:
    where = f"contest[{i}]"
    cid = _get(raw, "id", str, where)
    where = f"contest {cid!r}"
    prefix = f"{election.id}-"
    if not cid.startswith(prefix):
        raise ContestIndexError(
            f"{where}: id must start with {prefix!r}")
    kind = _get(raw, "kind", str, where)
    if kind not in KINDS:
        raise ContestIndexError(
            f"{where}: kind must be one of {sorted(KINDS)}, got {kind!r}")
    division = _get(raw, "division", str, where)
    if not division.startswith("ocd-division/"):
        raise ContestIndexError(
            f"{where}: division must start with 'ocd-division/'")
    number = _get(raw, "number", str, where, None)
    office = _get(raw, "office", str, where, None)
    if kind == "measure":
        # A measure's `number` is its ballot designation; a ballot that
        # numbers none (North Carolina heads each only "Constitutional
        # Amendment") leaves it out, and its measures keep file order.
        if office is not None:
            raise ContestIndexError(f"{where}: measure must not set 'office'")
    else:
        if office is None:
            raise ContestIndexError(f"{where}: race needs 'office'")
        if number is not None:
            raise ContestIndexError(f"{where}: race must not set 'number'")
    dir_name = cid[len(prefix):]
    if dir_name == CRASH_COURSE:
        raise ContestIndexError(
            f"{where}: {CRASH_COURSE!r} is the crash course's id, derived "
            f"from the statewide measures; it is not listed here")
    entry = IndexEntry(
        id=cid,
        kind=kind,
        division=division,
        title=_get(raw, "title", str, where),
        number=number,
        office=office,
        corrections=_load_corrections(raw, where),
        choice=_is_choice_question(election_dir / dir_name),
    )
    _check_sources_match(entry, election, election_dir / dir_name, where)
    return entry


def load_index(election_dir: str | Path) -> ContestIndex:
    """Load `<election_dir>/contests.toml`, or raise ContestIndexError."""
    election_dir = Path(election_dir)
    path = election_dir / "contests.toml"
    data = _read_toml(path)
    election = _load_election(data, path)
    entries = []
    seen: set[str] = set()
    for i, raw in enumerate(_get(data, "contest", list, str(path), [])):
        if not isinstance(raw, dict):
            raise ContestIndexError(f"contest[{i}]: must be a table")
        entry = _load_entry(raw, i, election, election_dir)
        if entry.id in seen:
            raise ContestIndexError(f"contest {entry.id!r}: duplicate id")
        seen.add(entry.id)
        entries.append(entry)
    from .crash_course import crash_course_entry
    return ContestIndex(
        election=election, entries=tuple(entries),
        crash_course=crash_course_entry(election, tuple(entries),
                                        election_dir))


def key_for(election_id: str, entry: IndexEntry,
           standard) -> tuple[str, str, str, int, int] | None:
    """The cache key (docs/ARCHITECTURE.md) for `entry`, or None if its
    kind has no template yet (so it cannot be generated). A crash course's
    contest id carries a digest of its members' scripts and narration
    (ballotreels.crash_course.key_contest), so a change to any of them is
    a new key, never the old video."""
    if entry.kind == CRASH_COURSE:
        from . import crash_course
        return (election_id, entry.division, crash_course.key_contest(entry),
                standard.version, crash_course.TEMPLATE_VERSION)
    templates = TEMPLATES.get(entry.kind)
    if not templates:
        return None
    template_version = max(templates)
    return (election_id, entry.division, entry.id, standard.version,
            template_version)


def key_string(key: tuple[str, str, str, int, int]) -> str:
    """The canonical string form of a cache key, used as the queue's job
    key and in logs."""
    election_id, division, contest_id, standard_version, template_version = key
    return f"{election_id}|{division}|{contest_id}|s{standard_version}|t{template_version}"


def level_of(division: str, state_division: str) -> str:
    """Which ballot level `division` belongs to: one of LEVELS, or
    "other" if it matches none of them."""
    if division == state_division:
        return "state"
    for level in ("cd", "sldu", "sldl", "county"):
        if f"/{level}:" in division:
            return level
    return "other"


def _number_key(number: str | None, position: int) -> tuple[int, Any]:
    if number is None:
        return (2, position)
    return (0, int(number)) if number.isdigit() else (1, number)


def ballot_order(index: ContestIndex) -> tuple[IndexEntry, ...]:
    """Every entry, grouped by level in the fixed order the brief gives
    (statewide, congressional, legislative, county), races in file order
    then measures in natural number order within each level (any
    unnumbered ones after, in file order)."""
    level_rank = {level: i for i, level in enumerate(LEVELS)}
    file_order = {entry.id: i for i, entry in enumerate(index.entries)}

    def key(entry: IndexEntry):
        level = level_of(entry.division, index.election.state)
        lrank = level_rank.get(level, len(LEVELS))
        if entry.kind == "race":
            return (lrank, 0, file_order[entry.id])
        return (lrank, 1, _number_key(entry.number, file_order[entry.id]))

    return tuple(sorted(index.entries, key=key))
