"""Load a contest directory: data/<election>/<contest>/.

The format is docs/SCRIPT-FORMAT.md. The loader only checks shape (files
exist, TOML parses, keys have the right types) and raises ContestError
when the data cannot be read at all. Whether the data meets the standard
is the checks' job (ballotreels.checks), which report every failure.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MISSING = object()


class ContestError(Exception):
    """A contest directory that cannot be loaded."""


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    publisher: str
    url: str
    file: str
    retrieved: str
    credit: str | None = None  # None when the key is absent
    # a university guide's publisher as each line relying on it names it
    # ("University of Arkansas"); None when the key is absent
    short_name: str | None = None

    @property
    def short_credit(self) -> str:
        """How a chart names this source under it: `credit`, or the full
        `publisher` when it has none (docs/SCRIPT-FORMAT.md)."""
        return self.credit if self.credit is not None else self.publisher


@dataclass(frozen=True)
class Visual:
    """A line's visual (a chart, a timeline, an illustration or the page), as
    written. Each field is None when its key is absent;
    the values are not type-checked here, since a malformed chart is a check
    failure (ballotreels.checks.check_visuals), not a load error."""
    kind: Any = None
    title: Any = None
    source: Any = None
    unit: Any = None
    labels: Any = None
    values: Any = None
    figure: Any = None
    items: Any = None  # timeline: one entry per label
    name: Any = None   # illustration: an entry in the illustration library
    focus: Any = None  # page: the phrase on the card to circle
    highlight: Any = None  # page: phrases on the card to highlight
    stamp: Any = None  # illustration: short words written across its top


VISUAL_KEYS = tuple(Visual.__dataclass_fields__)


@dataclass(frozen=True)
class Card:
    """The script's `[card]`: the top of the measure's official page,
    quoted verbatim (docs/SCRIPT-FORMAT.md). As with Visual, each field is
    None when its key is absent, and the checks judge the values."""
    source: Any = None
    number: Any = None
    title: Any = None
    origin: Any = None
    summary: Any = None
    fiscal: Any = None  # optional: the fiscal statement, under its own heading
    yes: Any = None     # optional, with `no`: what each vote means
    no: Any = None

    # The fields quoted from the source, in the order the page shows them.
    QUOTED = ("title", "origin", "summary", "fiscal", "yes", "no")
    # The fields a card may leave out.
    OPTIONAL = ("fiscal", "yes", "no")

    def quoted(self) -> tuple[tuple[str, Any], ...]:
        """(key, value) for each quoted field, in page order."""
        return tuple((k, getattr(self, k)) for k in self.QUOTED)


CARD_KEYS = tuple(Card.__dataclass_fields__)


@dataclass(frozen=True)
class Choice:
    """One of a choice question's options, as the ballot prints it
    (docs/SCRIPT-FORMAT.md). As with Visual, each field is None when its
    key is absent, and the checks judge the values."""
    letter: Any = None        # as printed, "(a)"; all choices or none
    label: Any = None         # verbatim, drawn on the card and the grid
    spoken: Any = None        # as narrated; None: the label
    illustration: Any = None  # its drawing on the grid, from the library

    @property
    def said(self) -> Any:
        """The name the narration says: `spoken`, or the label."""
        return self.label if self.spoken is None else self.spoken

    @property
    def printed(self) -> str:
        """The letter and label as the ballot prints them: "(a) ..."."""
        parts = (self.letter, self.label)
        return " ".join(p for p in parts if isinstance(p, str) and p)


CHOICE_KEYS = tuple(Choice.__dataclass_fields__)


@dataclass(frozen=True)
class Choices:
    """The script's `[choices]`: the options of a question that asks voters
    to pick one of several, rather than yes or no, in ballot order. A
    script with this table is a choice question."""
    source: Any = None
    choices: tuple[Choice, ...] = ()


@dataclass(frozen=True)
class Name:
    """A person or organisation a line names, declared with its role in the
    record and the source that names it (docs/SCRIPT-FORMAT.md, STANDARD.md
    section 9). As with Visual, each field is None when its key is absent,
    and the checks judge the values."""
    name: Any = None    # as said, and verbatim in the source
    role: Any = None    # its role in the record, as said
    source: Any = None  # a source id the line cites, that names it


NAME_KEYS = tuple(Name.__dataclass_fields__)


@dataclass(frozen=True)
class Line:
    text: str
    sources: tuple[str, ...] | None  # None when the key is absent
    connective: bool
    visual: Visual | None = None
    # A side's line: the passages of its cited argument it distils, each
    # verbatim (docs/SCRIPT-FORMAT.md). None when the key is absent.
    basis: tuple[str, ...] | None = None
    # Every person or organisation the line names (STANDARD.md section 9).
    names: tuple[Name, ...] = ()


@dataclass(frozen=True)
class Section:
    id: str
    heading: str
    side: str | None
    lines: tuple[Line, ...]
    filed: bool = True


@dataclass(frozen=True)
class Script:
    contest: str
    template: str
    template_version: int
    standard_version: int
    sections: tuple[Section, ...]
    card: Card | None = None  # None when there is no [card] table
    # None when there is no [choices] table: a yes/no question
    choices: Choices | None = None

    def labels(self) -> tuple[str, ...]:
        """Each section's label, in file order: its id, or `id[k]` for the
        k-th (0-based) of several sections sharing an id (template 2's
        background sections), so a failure can say which one it means."""
        counts: dict[str, int] = {}
        for sec in self.sections:
            counts[sec.id] = counts.get(sec.id, 0) + 1
        seen: dict[str, int] = {}
        out = []
        for sec in self.sections:
            if counts[sec.id] == 1:
                out.append(sec.id)
            else:
                k = seen.get(sec.id, 0)
                seen[sec.id] = k + 1
                out.append(f"{sec.id}[{k}]")
        return tuple(out)

    def labelled(self) -> tuple[tuple[str, Section], ...]:
        """(label, section) pairs, in file order; see labels()."""
        return tuple(zip(self.labels(), self.sections))


@dataclass(frozen=True)
class Contest:
    path: Path
    id: str
    election: str
    division: str
    kind: str
    title: str
    sources: tuple[Source, ...]
    script: Script

    def source(self, source_id: str) -> Source | None:
        for s in self.sources:
            if s.id == source_id:
                return s
        return None


def _get(table: dict[str, Any], key: str, typ: type, where: str,
         default: Any = _MISSING) -> Any:
    if key not in table:
        if default is _MISSING:
            raise ContestError(f"{where}: missing key {key!r}")
        return default
    value = table[key]
    # bool is a subclass of int; do not let `true` pass as a version number.
    if not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
        raise ContestError(
            f"{where}: {key!r} must be {typ.__name__}, "
            f"got {type(value).__name__}")
    return value


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise ContestError(f"{path.name}: not found") from None
    except tomllib.TOMLDecodeError as e:
        raise ContestError(f"{path.name}: {e}") from None


def _load_sources(path: Path) -> tuple[dict[str, Any], tuple[Source, ...]]:
    data = _read_toml(path)
    contest = _get(data, "contest", dict, path.name)
    sources = []
    seen = set()
    for i, raw in enumerate(_get(data, "source", list, path.name, [])):
        where = f"{path.name}: source[{i}]"
        if not isinstance(raw, dict):
            raise ContestError(f"{where}: must be a table")
        src = Source(**{k: _get(raw, k, str, where) for k in
                        ("id", "kind", "publisher", "url", "file",
                         "retrieved")},
                     credit=_get(raw, "credit", str, where, None),
                     short_name=_get(raw, "short_name", str, where, None))
        if src.id in seen:
            raise ContestError(f"{where}: duplicate source id {src.id!r}")
        seen.add(src.id)
        sources.append(src)
    return contest, tuple(sources)


def _load_line(raw: Any, where: str) -> Line:
    if not isinstance(raw, dict):
        raise ContestError(f"{where}: must be a table")
    sources = _get(raw, "sources", list, where, None)
    if sources is not None:
        if not all(isinstance(s, str) for s in sources):
            raise ContestError(f"{where}: 'sources' must be a list of strings")
        sources = tuple(sources)
    basis = _get(raw, "basis", list, where, None)
    if basis is not None:
        if not all(isinstance(b, str) for b in basis):
            raise ContestError(f"{where}: 'basis' must be a list of strings")
        basis = tuple(basis)
    names = []
    for k, n in enumerate(_get(raw, "names", list, where, [])):
        if not isinstance(n, dict):
            raise ContestError(f"{where}: names[{k}] must be a table")
        names.append(Name(**{key: n[key] for key in NAME_KEYS if key in n}))
    return Line(
        text=_get(raw, "text", str, where),
        sources=sources,
        connective=_get(raw, "connective", bool, where, False),
        visual=_load_visual(raw, where),
        basis=basis,
        names=tuple(names),
    )


def _load_visual(line: dict[str, Any], where: str) -> Visual | None:
    raw = _get(line, "visual", dict, where, None)
    if raw is None:
        return None
    return Visual(**{k: raw[k] for k in VISUAL_KEYS if k in raw})


def _load_script(path: Path) -> Script:
    data = _read_toml(path)
    name = path.name
    sections = []
    for i, raw in enumerate(_get(data, "section", list, name, [])):
        where = f"{name}: section[{i}]"
        if not isinstance(raw, dict):
            raise ContestError(f"{where}: must be a table")
        sid = _get(raw, "id", str, where)
        where = f"{name}: section {sid!r}"
        lines = tuple(
            _load_line(line, f"{where} line[{j}]")
            for j, line in enumerate(_get(raw, "line", list, where, [])))
        sections.append(Section(
            id=sid,
            heading=_get(raw, "heading", str, where),
            side=_get(raw, "side", str, where, None),
            lines=lines,
            filed=_get(raw, "filed", bool, where, True),
        ))
    raw_card = _get(data, "card", dict, name, None)
    card = (None if raw_card is None else
            Card(**{k: raw_card[k] for k in CARD_KEYS if k in raw_card}))
    return Script(
        choices=_load_choices(data, name),
        contest=_get(data, "contest", str, name),
        template=_get(data, "template", str, name),
        template_version=_get(data, "template_version", int, name),
        standard_version=_get(data, "standard_version", int, name),
        sections=tuple(sections),
        card=card,
    )


def _load_choices(data: dict[str, Any], name: str) -> Choices | None:
    raw = _get(data, "choices", dict, name, None)
    if raw is None:
        return None
    where = f"{name}: [choices]"
    out = []
    for i, c in enumerate(_get(raw, "choice", list, where, [])):
        if not isinstance(c, dict):
            raise ContestError(f"{where} choice[{i}]: must be a table")
        out.append(Choice(**{k: c[k] for k in CHOICE_KEYS if k in c}))
    return Choices(source=raw.get("source"), choices=tuple(out))


def load_contest(path: str | Path) -> Contest:
    """Load the contest in directory `path`, or raise ContestError."""
    path = Path(path)
    if not path.is_dir():
        raise ContestError("not a directory")
    meta, sources = _load_sources(path / "sources.toml")
    where = "sources.toml: [contest]"
    return Contest(
        path=path,
        id=_get(meta, "id", str, where),
        election=_get(meta, "election", str, where),
        division=_get(meta, "division", str, where),
        kind=_get(meta, "kind", str, where),
        title=_get(meta, "title", str, where),
        sources=sources,
        script=_load_script(path / "script.toml"),
    )
