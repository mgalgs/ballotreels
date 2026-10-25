"""The standard's machine checks on a contest's script and sources.

check_contest() runs every check and returns every failure; an empty
list means the contest passes. Checks that need data another check found
broken (say, side parity without exactly one yes and one no section)
skip that part rather than report the same defect twice.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from . import narration
from .contest import Contest, Line, Section, Visual
from .standard import (BACKGROUND, BACKGROUND_ONLY_KINDS, SOURCE_KINDS,
                       TEMPLATES, Standard, Template, judgment_word_pattern,
                       load_standard)

SIDE_TOLERANCE = 0.05
AIRTIME_TOLERANCE = 0.05
CHART_KINDS = ("bars", "share", "series", "figure")
VISUAL_KINDS = (*CHART_KINDS, "number", "timeline", "words")
MAX_SHOWN_WORDS = 6  # a number's label, a words visual's phrase


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
            cited = [("cites", sid) for sid in line.sources or ()]
            if line.visual is not None and isinstance(line.visual.source, str):
                cited.append(("has a chart citing", line.visual.source))
            for verb, sid in cited:
                src = c.source(sid)
                if src is not None and src.kind in BACKGROUND_ONLY_KINDS:
                    out.append(Failure(
                        "background-only",
                        f"{verb} {sid!r}, of kind {src.kind!r}, which may be "
                        f"cited only in a {BACKGROUND!r} section",
                        label, i))
    return out


def _is_number(x: object) -> bool:
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x))


def _string_list(v: Visual, key: str, out: list[str]) -> bool:
    """Whether `v`'s `key` is a list of strings; reports it to `out` if not."""
    value = getattr(v, key)
    if value is None:
        out.append(f"has no {key!r}")
    elif (not isinstance(value, list)
          or not all(isinstance(x, str) for x in value)):
        out.append(f"{key!r} must be a list of strings")
    else:
        return True
    return False


def _forbid(v: Visual, keys: tuple[str, ...], out: list[str]) -> None:
    for key in keys:
        if getattr(v, key) is not None:
            out.append(f"a {v.kind!r} visual may not have {key!r}")


def _short_text(v: Visual, key: str, out: list[str]) -> bool:
    """`v`'s `key` is a non-empty string of at most MAX_SHOWN_WORDS words."""
    value = getattr(v, key)
    if value is None:
        out.append(f"has no {key!r}")
    elif not isinstance(value, str) or not value.strip():
        out.append(f"{key!r} must be a non-empty string")
    else:
        n = len(value.split())
        if n > MAX_SHOWN_WORDS:
            out.append(f"{key!r} has {n} words, more than "
                       f"{MAX_SHOWN_WORDS}")
        return True
    return False


def _number_problems(line: Line, v: Visual) -> list[str]:
    """A `number`: its figure says nothing the narrator does not."""
    out = []
    _forbid(v, ("title", "unit", "labels", "values", "figure", "items"), out)
    if _short_text(v, "text", out):
        said = set(re.findall(r"\d+", line.text))
        for run in re.findall(r"\d+", v.text):
            if run not in said:
                out.append(f"'text' {v.text!r} shows {run!r}, which the "
                           f"line's text does not say")
        if not re.search(r"\d", v.text):
            out.append(f"'text' {v.text!r} has no number in it")
    _short_text(v, "label", out)
    return out


def _words_problems(line: Line, v: Visual) -> list[str]:
    """`words`: a phrase lifted verbatim from the line."""
    out = []
    _forbid(v, ("title", "source", "unit", "labels", "values", "figure",
                "label", "items"), out)
    if (_short_text(v, "text", out)
            and v.text.casefold() not in line.text.casefold()):
        out.append(f"'text' {v.text!r} is not in the line's text")
    return out


def _timeline_problems(v: Visual) -> list[str]:
    out = []
    _forbid(v, ("title", "unit", "values", "figure", "text", "label"), out)
    labels_ok = _string_list(v, "labels", out)
    items_ok = _string_list(v, "items", out)
    if labels_ok and items_ok:
        if len(v.labels) != len(v.items):
            out.append(f"has {len(v.labels)} labels but {len(v.items)} "
                       f"items")
        elif len(v.labels) < 2:
            out.append("a 'timeline' needs at least 2 entries")
    return out


def _source_problems(c: Contest, line: Line, v: Visual) -> list[str]:
    out = []
    if v.source is None:
        return ["has no 'source'"]
    if not isinstance(v.source, str) or not v.source:
        return ["'source' must be a non-empty string"]
    src = c.source(v.source)
    if src is None:
        out.append(f"cites {v.source!r}, which is not in sources.toml")
    else:
        if src.kind not in SOURCE_KINDS:
            out.append(f"cites {v.source!r}, of kind {src.kind!r}, which "
                       f"is not an allowed kind")
        if v.source not in (line.sources or ()):
            out.append(f"cites {v.source!r}, which is not among the "
                       f"line's sources")
    return out


def _visual_problems(c: Contest, line: Line, v: Visual) -> list[str]:
    """Everything wrong with visual `v` on `line`, per
    docs/SCRIPT-FORMAT.md."""
    if v.kind is None:
        return ["has no 'kind'"]
    if v.kind not in VISUAL_KINDS:
        if isinstance(v.kind, str) and v.kind:
            return [f"kind {v.kind!r} is not one of "
                    f"{', '.join(VISUAL_KINDS)}"]
        return ["'kind' must be a non-empty string"]

    if v.kind == "words":  # no source of its own: the line cites
        return _words_problems(line, v)
    out = []
    if v.kind in CHART_KINDS:
        if v.title is None:
            out.append("has no 'title'")
        elif not isinstance(v.title, str) or not v.title:
            out.append("'title' must be a non-empty string")
    out += _source_problems(c, line, v)
    if v.kind == "number":
        return out + _number_problems(line, v)
    if v.kind == "timeline":
        return out + _timeline_problems(v)

    if v.kind == "figure":
        if v.figure is None:
            out.append("a 'figure' chart has no 'figure'")
        elif not isinstance(v.figure, str) or not v.figure:
            out.append("'figure' must be a non-empty string")
        for key in ("labels", "values", "unit", "text", "label", "items"):
            if getattr(v, key) is not None:
                out.append(f"a 'figure' chart may not have {key!r}")
        return out

    if v.figure is not None:
        out.append(f"a {v.kind!r} chart may not have 'figure'")
    _forbid(v, ("text", "label", "items"), out)
    if v.unit is None:
        out.append("has no 'unit'")
    elif not isinstance(v.unit, str):
        out.append("'unit' must be a string")
    labels_ok = _string_list(v, "labels", out)
    values_ok = False
    if v.values is None:
        out.append("has no 'values'")
    elif (not isinstance(v.values, list)
          or not all(_is_number(x) for x in v.values)):
        out.append("'values' must be a list of numbers")
    else:
        values_ok = True
    if labels_ok and values_ok and len(v.labels) != len(v.values):
        out.append(f"has {len(v.labels)} labels but {len(v.values)} values")
    if values_ok and v.kind in ("bars", "share"):
        if any(x < 0 for x in v.values):
            out.append(f"a {v.kind!r} chart's values must be >= 0")
        elif v.kind == "share" and sum(v.values) > 100 + 1e-9:
            out.append(f"a 'share' chart's values sum to {sum(v.values):g}, "
                       f"more than 100")
    if labels_ok and v.kind == "series":
        if not all(re.fullmatch(r"\d+", x) for x in v.labels):
            out.append("a 'series' chart's labels must be years")
        else:
            steps = {int(b) - int(a) for a, b in zip(v.labels, v.labels[1:])}
            if len(steps) > 1 or any(d <= 0 for d in steps):
                out.append("a 'series' chart's years must increase evenly")
    return out


def check_visuals(c: Contest) -> list[Failure]:
    """Every visual is well formed, and every one but `words` cites one of
    its line's sources (docs/SCRIPT-FORMAT.md; STANDARD.md 7.1). A number
    or a words visual shows nothing the narrator does not say."""
    out = []
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            if line.visual is None:
                continue
            what = ("chart" if line.visual.kind in CHART_KINDS
                    or line.visual.kind not in VISUAL_KINDS
                    else f"{line.visual.kind!r} visual")
            for msg in _visual_problems(c, line, line.visual):
                out.append(Failure("visual", f"{what} {msg}", label, i))
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


def check_side_visuals(c: Contest) -> list[Failure]:
    """STANDARD.md 7.3: a visual in a side section only if the other side
    has visuals of the same kinds (as many of each): a chart, number or
    timeline matched by one of its kind, words by as many words."""
    by_side: dict[str, list[tuple[str, Section]]] = {}
    for label, sec in c.script.labelled():
        if sec.side is not None:
            by_side.setdefault(sec.side, []).append((label, sec))
    yes, no = by_side.get("yes", []), by_side.get("no", [])
    if len(yes) != 1 or len(no) != 1:
        return []  # a template failure; nothing to compare

    def kinds(sec: Section) -> Counter:
        return Counter(k if isinstance(k, str) else repr(k)
                       for k in (ln.visual.kind for ln in sec.lines
                                 if ln.visual is not None))

    have = {"yes": kinds(yes[0][1]), "no": kinds(no[0][1])}
    if have["yes"] == have["no"]:
        return []

    def show(counts: Counter) -> str:
        return ", ".join(sorted(counts.elements())) or "none"

    out = []
    for label, sec in (yes[0], no[0]):
        for i, line in enumerate(sec.lines):
            if line.visual is not None:
                out.append(Failure(
                    "side-visual",
                    f"a visual in a side section needs visuals of the same "
                    f"kinds on both sides: yes has {show(have['yes'])}, "
                    f"no has {show(have['no'])}",
                    label, i))
    return out


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
    """STANDARD.md 3.1: no judgment word in a heading, a line or anything
    a visual shows."""
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
            if line.visual is not None:
                for key, value in _shown_text(line.visual):
                    scan(value, f"visual {key}", label, i)
    return out


def _shown_text(v: Visual) -> list[tuple[str, str]]:
    """The words a visual puts on screen, as (key, text) pairs."""
    out = []
    for key in ("title", "text", "label", "labels", "items"):
        value = getattr(v, key)
        for x in value if isinstance(value, list) else [value]:
            if isinstance(x, str):
                out.append((key, x))
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
        *check_visuals(c),
        *check_sources(c),
        *check_template(c),
        *check_side_parity(c),
        *check_side_visuals(c),
        *check_airtime(c),
        *check_judgment_words(c, standard.judgment_words),
        *check_standard_version(c, standard.version),
    ]
