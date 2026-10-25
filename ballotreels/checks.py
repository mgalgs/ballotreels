"""The standard's machine checks on a contest's script and sources.

check_contest() runs every check and returns every failure; an empty
list means the contest passes. Checks that need data another check found
broken (say, side parity without exactly one yes and one no section)
skip that part rather than report the same defect twice.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import narration
from .contest import Contest, Section
from .standard import (BACKGROUND, BACKGROUND_ONLY_KINDS, SOURCE_KINDS,
                       TEMPLATES, Standard, Template, judgment_word_pattern,
                       load_standard)

SIDE_TOLERANCE = 0.05
AIRTIME_TOLERANCE = 0.05


@dataclass(frozen=True)
class Failure:
    check: str
    message: str
    section: str | None = None  # section label (Script.labels), if in one
    line: int | None = None     # 0-based index into that section's lines

    def __str__(self) -> str:
        where = ""
        if self.section is not None:
            where = self.section
            if self.line is not None:
                where += f".line[{self.line}]"
            where += ": "
        return f"[{self.check}] {where}{self.message}"


def word_count(section: Section) -> int:
    """Whitespace-split words over all of a section's lines' text."""
    return sum(len(line.text.split()) for line in section.lines)


def check_contest_id(c: Contest) -> list[Failure]:
    if c.script.contest == c.id:
        return []
    return [Failure("contest-id",
                    f"script.toml contest {c.script.contest!r} does not "
                    f"match sources.toml id {c.id!r}")]


def check_line_citations(c: Contest) -> list[Failure]:
    out = []
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            cited = bool(line.sources)
            if cited and line.connective:
                msg = "has both sources and connective = true"
            elif not cited and not line.connective:
                msg = ("has an empty sources list"
                       if line.sources is not None
                       else "has neither sources nor connective = true")
            else:
                continue
            out.append(Failure("line-citation", msg, label, i))
    return out


def check_cited_sources_exist(c: Contest) -> list[Failure]:
    known = {s.id for s in c.sources}
    out = []
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            for sid in line.sources or ():
                if sid not in known:
                    out.append(Failure(
                        "cited-source",
                        f"cites {sid!r}, which is not in sources.toml",
                        label, i))
    return out


def check_background_only(c: Contest) -> list[Failure]:
    """STANDARD.md 6.1: a line cites a background-only kind of source only
    in a background section. Unknown ids are check_cited_sources_exist's."""
    out = []
    for label, sec in c.script.labelled():
        if sec.id == BACKGROUND:
            continue
        for i, line in enumerate(sec.lines):
            for sid in line.sources or ():
                src = c.source(sid)
                if src is not None and src.kind in BACKGROUND_ONLY_KINDS:
                    out.append(Failure(
                        "background-only",
                        f"cites {sid!r}, of kind {src.kind!r}, which may be "
                        f"cited only in a {BACKGROUND!r} section",
                        label, i))
    return out


def check_sources(c: Contest) -> list[Failure]:
    out = []
    root = c.path.resolve()
    for s in c.sources:
        if s.kind not in SOURCE_KINDS:
            out.append(Failure("source",
                               f"source {s.id!r} has kind {s.kind!r}, "
                               f"which is not an allowed kind"))
        path = (c.path / s.file).resolve()
        if not path.is_relative_to(root):
            out.append(Failure("source",
                               f"source {s.id!r} file {s.file!r} is outside "
                               f"the contest directory"))
        elif not path.is_file():
            out.append(Failure("source",
                               f"source {s.id!r} file {s.file!r} does not "
                               f"exist"))
    return out


def _fits(got: tuple[str, ...], t: Template) -> bool:
    """Whether section ids `got` follow template `t`'s order, each repeated
    id filling its slot with zero or more sections."""
    pos = 0
    for sid in t.sections:
        if sid in t.repeated:
            while pos < len(got) and got[pos] == sid:
                pos += 1
        elif pos < len(got) and got[pos] == sid:
            pos += 1
        else:
            return False
    return pos == len(got)


def check_template(c: Contest) -> list[Failure]:
    sc = c.script
    versions = TEMPLATES.get(sc.template)
    if versions is None:
        return [Failure("template", f"unknown template {sc.template!r}")]
    t = versions.get(sc.template_version)
    if t is None:
        return [Failure("template",
                        f"unknown version {sc.template_version} of template "
                        f"{sc.template!r}")]
    out = []
    got = tuple(s.id for s in sc.sections)
    if not _fits(got, t):
        want = ", ".join(f"{sid}*" if sid in t.repeated else sid
                         for sid in t.sections)
        note = " (* zero or more)" if t.repeated else ""
        out.append(Failure("template",
                           f"sections are {', '.join(got) or '(none)'}; "
                           f"{sc.template} v{sc.template_version} requires "
                           f"{want}{note}"))
    for label, sec in sc.labelled():
        want = t.sides.get(sec.id)
        if sec.side != want:
            if want is None:
                msg = f"has side = {sec.side!r} but is not a side section"
            else:
                msg = f"must have side = {want!r}, has {sec.side!r}"
            out.append(Failure("template", msg, label))
    return out


def check_side_parity(c: Contest) -> list[Failure]:
    by_side: dict[str, list[Section]] = {}
    for sec in c.script.sections:
        if sec.side is not None:
            by_side.setdefault(sec.side, []).append(sec)
    yes, no = by_side.get("yes", []), by_side.get("no", [])
    if len(yes) != 1 or len(no) != 1:
        return []  # a template failure; nothing to compare
    a, b = word_count(yes[0]), word_count(no[0])
    if abs(a - b) <= SIDE_TOLERANCE * max(a, b):
        return []
    return [Failure("side-parity",
                    f"side word counts differ by more than 5% of the "
                    f"larger: {yes[0].id}={a}, {no[0].id}={b}")]


def check_airtime(c: Contest) -> list[Failure]:
    """STANDARD.md 2.2/4.1: the two sides' spoken durations within 5% of the
    larger, measured from the narration sidecars' phrase times.

    Silently reports nothing when there are no sidecars yet, or when they no
    longer line up with the script (narration.NarrationError): a stale
    sidecar can't tell us anything about the current script's airtime: it is
    not this check's job to say the narration is stale, only to measure it
    when it can.
    """
    try:
        durations = narration.side_durations(c)
    except ImportError:
        return []
    except narration.NarrationError:
        return []
    except KeyError:
        return []  # an unknown template/version; check_template reports it
    if durations is None:
        return []
    (side_a, dur_a), (side_b, dur_b) = durations
    if abs(dur_a - dur_b) <= AIRTIME_TOLERANCE * max(dur_a, dur_b):
        return []
    return [Failure("airtime",
                    f"side spoken durations differ by more than 5% of the "
                    f"larger: {side_a}={dur_a:.1f}s, {side_b}={dur_b:.1f}s")]


def check_judgment_words(c: Contest, words: tuple[str, ...]) -> list[Failure]:
    if not words:
        return []
    pattern = judgment_word_pattern(words)
    out = []

    def scan(text, what, section, line):
        for m in pattern.finditer(text):
            out.append(Failure("judgment-word",
                               f"judgment word {m.group(0)!r} in {what}",
                               section, line))

    for label, sec in c.script.labelled():
        scan(sec.heading, "heading", label, None)
        for i, line in enumerate(sec.lines):
            scan(line.text, "text", label, i)
    return out


def check_standard_version(c: Contest, version: int) -> list[Failure]:
    if c.script.standard_version == version:
        return []
    return [Failure("standard-version",
                    f"script is under standard version "
                    f"{c.script.standard_version}; the current version is "
                    f"{version}")]


def check_contest(c: Contest, standard: Standard | None = None
                  ) -> list[Failure]:
    """Run every machine check on `c`; return all failures, in check order."""
    if standard is None:
        standard = load_standard()
    return [
        *check_contest_id(c),
        *check_line_citations(c),
        *check_cited_sources_exist(c),
        *check_background_only(c),
        *check_sources(c),
        *check_template(c),
        *check_side_parity(c),
        *check_airtime(c),
        *check_judgment_words(c, standard.judgment_words),
        *check_standard_version(c, standard.version),
    ]
