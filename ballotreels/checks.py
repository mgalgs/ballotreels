"""The standard's machine checks on a contest's script and sources.

check_contest() runs every check and returns every failure; an empty
list means the contest passes. Checks that need data another check found
broken (say, side parity without exactly one yes and one no section)
skip that part rather than report the same defect twice.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contest import Contest, Section
from .standard import (SOURCE_KINDS, Standard, judgment_word_pattern,
                       load_standard)

# template -> version -> section ids in order, and which of them are sides.
TEMPLATES: dict[str, dict[int, tuple[tuple[str, ...], dict[str, str]]]] = {
    "measure": {
        1: (("what", "today", "change", "fiscal", "yes", "no", "vote"),
            {"yes": "yes", "no": "no"}),
    },
}

SIDE_TOLERANCE = 0.05


@dataclass(frozen=True)
class Failure:
    check: str
    message: str
    section: str | None = None  # section id, when the failure is in one
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
    for sec in c.script.sections:
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
            out.append(Failure("line-citation", msg, sec.id, i))
    return out


def check_cited_sources_exist(c: Contest) -> list[Failure]:
    known = {s.id for s in c.sources}
    out = []
    for sec in c.script.sections:
        for i, line in enumerate(sec.lines):
            for sid in line.sources or ():
                if sid not in known:
                    out.append(Failure(
                        "cited-source",
                        f"cites {sid!r}, which is not in sources.toml",
                        sec.id, i))
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


def check_template(c: Contest) -> list[Failure]:
    sc = c.script
    versions = TEMPLATES.get(sc.template)
    if versions is None:
        return [Failure("template", f"unknown template {sc.template!r}")]
    if sc.template_version not in versions:
        return [Failure("template",
                        f"unknown version {sc.template_version} of template "
                        f"{sc.template!r}")]
    ids, sides = versions[sc.template_version]
    out = []
    got = tuple(s.id for s in sc.sections)
    if got != ids:
        out.append(Failure("template",
                           f"sections are {', '.join(got) or '(none)'}; "
                           f"{sc.template} v{sc.template_version} requires "
                           f"{', '.join(ids)}"))
    for sec in sc.sections:
        want = sides.get(sec.id)
        if sec.side != want:
            if want is None:
                msg = f"has side = {sec.side!r} but is not a side section"
            else:
                msg = f"must have side = {want!r}, has {sec.side!r}"
            out.append(Failure("template", msg, sec.id))
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

    for sec in c.script.sections:
        scan(sec.heading, "heading", sec.id, None)
        for i, line in enumerate(sec.lines):
            scan(line.text, "text", sec.id, i)
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
        *check_sources(c),
        *check_template(c),
        *check_side_parity(c),
        *check_judgment_words(c, standard.judgment_words),
        *check_standard_version(c, standard.version),
    ]
