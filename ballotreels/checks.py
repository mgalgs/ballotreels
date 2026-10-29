"""The standard's machine checks on a contest's script and sources.

check_contest() runs every check and returns every failure; an empty
list means the contest passes. Checks that need data another check found
broken (say, side parity without exactly one yes and one no section)
skip that part rather than report the same defect twice.
"""

from __future__ import annotations

import difflib
import html
import math
import re
import shutil
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from . import grid, narration, spoken, storyboard
from .ballots import BALLOTS, Ballot, badge, ballot_for, guide_of
from .contest import CARD_KEYS, Card, Choice, Contest, Line, Section, Visual
from .geo import divisions
from .geo.lookup import ballot_division
from .illustrations import load_library
from .index import voters_problem
from .printed import number, with_unit
from .standard import (BACKGROUND, BACKGROUND_ONLY_KINDS, CHOICE_TEMPLATES,
                       CHOICES, FISCAL, NAMING_KINDS, PRECEDENT_RECORD,
                       SOURCE_KINDS, TEMPLATES, UNIVERSITY_GUIDE,
                       UNIVERSITY_GUIDE_SECTIONS, Risk, Standard,
                       Template, judgment_word_pattern, load_standard,
                       template_for)

SIDE_TOLERANCE = 0.05
CHART_KINDS = ("bars", "share", "series", "figure")
VISUAL_KINDS = (*CHART_KINDS, "timeline", "list", "illustration", "page",
                "choices")
# Kinds that only put text on screen: the centre of the frame is for
# pictures, so a script may no longer use them.
REMOVED_KINDS = ("number", "words")


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


def check_voters(c: Contest) -> list[Failure]:
    """A measure under a county that is not the county's own names who
    votes on it, in sources.toml's [contest] `voters`, and a contest with
    `voters` has a `[card]`, where the film says so
    (ballotreels.index.voters_problem)."""
    slug = c.id.removeprefix(f"{c.election}-")
    problem = voters_problem(c.kind, c.division, slug, c.voters)
    if problem is not None:
        return [Failure("voters", problem)]
    if c.voters is not None and c.script.card is None:
        return [Failure("voters",
                        "has 'voters' but no [card]: the card is where the "
                        "film says who votes on it")]
    return []


def check_division(c: Contest) -> list[Failure]:
    """A county, city or school district contest's division is one the
    geo build has a shape for, as listed in its election's divisions.tsv
    (ballotreels.geo.divisions): the zip lookup shows a contest only for
    a division it has a shape of, so one typed from the ballot ("San
    Diego Unified") rather than TIGER's name ("San Diego City Unified")
    would be shown to no voter. Other levels (the state, its legislative
    districts) are not listed and not checked.

    Not part of check_contest: the film worker runs that on a scratch
    copy of the contest dir with no election around it, and a division
    matters to the zip lookup, not the film. `python -m ballotreels
    check` runs it beside check_contest.

    A school district's 9-12-only piece (`<name>_9-12`) fails too, listed
    or not: the zip lookup counts a voter there as in the district
    (ballotreels.geo.lookup.ballot_division), so a contest naming the
    piece would reach only part of its electorate."""
    district = ballot_division(c.division)
    if district != c.division:
        return [Failure(
            "division",
            f"{c.id}: division {c.division!r} is only the district's "
            f"9-12 territory, and its voters see the district's contests; "
            f"use the plain district division {district!r}")]
    level, _, name = c.division.rsplit("/", 1)[-1].partition(":")
    if level not in divisions.LEVELS:
        return []
    election_dir = Path(c.path).resolve().parent
    path = election_dir / divisions.FILENAME
    if not path.is_file():
        return [Failure(
            "division",
            f"{c.id}: its election has no {divisions.FILENAME} to check "
            f"its {level} division {c.division!r} against; write it from "
            f"the geo build with `python -m ballotreels geo divisions "
            f"{election_dir.name}` (README)")]
    listed = divisions.read_divisions(path)
    if c.division in listed:
        return []
    prefix = c.division[:-len(name)]
    same_level = {d[len(prefix):]: d for d in listed if d.startswith(prefix)}
    close = [f"{same_level[n]!r} ({listed[same_level[n]]})"
             for n in difflib.get_close_matches(name, same_level, n=3)]
    hint = (f"closest listed: {', '.join(close)}" if close else
            f"no listed {level} is close")
    return [Failure(
        "division",
        f"{c.id}: division {c.division!r} is not in {path.name}, so the "
        f"zip lookup would show it to no voter (usually the ballot's "
        f"name for it, not TIGER's); {hint}")]


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
    in a background section, or (6.5) on a `fiscal` line beside the
    fiscal analysis whose figure it gives a scale to. Unknown ids are
    check_cited_sources_exist's."""
    out = []
    for label, sec in c.script.labelled():
        if sec.id == BACKGROUND:
            continue
        for i, line in enumerate(sec.lines):
            scales = sec.id == FISCAL and any(
                (s := c.source(sid)) is not None
                and s.kind == "official-fiscal-analysis"
                for sid in line.sources or ())
            cited = [] if scales else \
                [("cites", sid) for sid in line.sources or ()]
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


def check_university_guide(c: Contest) -> list[Failure]:
    """STANDARD.md 1.2: a public university's ballot guide is a source only
    where the state publishes no official voter guide (so the contest has
    no `official-argument` source), only for explanation (a `background`,
    `today` or `change` section) and the sides, never for the opening, a
    cost or the vote lines; and every line relying on it names its
    publisher, by the source's `short_name`, so a viewer never takes it
    for the state's own words."""
    guides = [s for s in c.sources if s.kind == UNIVERSITY_GUIDE]
    if not guides:
        return []
    out = []
    for s in guides:
        if s.short_name is None or not s.short_name.strip():
            out.append(Failure(
                "university-guide",
                f"source {s.id!r}, of kind {UNIVERSITY_GUIDE!r}, has no "
                f"'short_name': the publisher's name as each line relying "
                f"on it says it"))
    official = [s.id for s in c.sources if s.kind == "official-argument"]
    for label, sec in c.script.labelled():
        allowed = sec.side is not None or sec.id in UNIVERSITY_GUIDE_SECTIONS
        for i, line in enumerate(sec.lines):
            cited = [s for sid in line.sources or ()
                     if (s := c.source(sid)) is not None
                     and s.kind == UNIVERSITY_GUIDE]
            v = line.visual
            shown = (c.source(v.source) if v is not None
                     and isinstance(v.source, str) else None)
            if shown is not None and shown.kind == UNIVERSITY_GUIDE \
                    and shown not in cited:
                cited.append(shown)  # _source_problems reports it uncited
            for s in cited:
                def fail(msg):
                    out.append(Failure("university-guide", msg, label, i))

                if official:
                    fail(f"cites {s.id!r}, a university guide, but the "
                         f"contest has an official voter guide's arguments "
                         f"({', '.join(map(repr, official))}); the "
                         f"official guide is the source")
                if not allowed:
                    fail(f"cites {s.id!r}, a university guide, in a "
                         f"{sec.id!r} section: it may explain (in "
                         f"{', '.join(sorted(UNIVERSITY_GUIDE_SECTIONS))}) "
                         f"and give the sides, never the opening, a cost "
                         f"or the vote")
                name = s.short_name
                if isinstance(name, str) and name.strip() \
                        and name not in line.text:
                    fail(f"cites {s.id!r}, a university guide, but does "
                         f"not name its publisher: the line must say "
                         f"{name!r}")
    return out


def check_questions(c: Contest) -> list[Failure]:
    """STANDARD.md section 10: another government's record of a similar
    law (a `precedent-record` source) is cited, by a line or its chart,
    only in a background section (rules 1.2, 10.5); and each question in
    the script's `[[question]]` record (rule 10.1) is asked in words and
    either names the ids of the lines that answer it, every one of them a
    line's `id`, or is marked `unanswered = true`, never both and never
    neither. Line ids are unique, so a question's answer is one line."""
    sc = c.script
    out = []
    for label, sec in sc.labelled():
        if sec.id == BACKGROUND:
            continue
        for i, line in enumerate(sec.lines):
            cited = [("cites", sid) for sid in line.sources or ()]
            if line.visual is not None and isinstance(line.visual.source, str):
                cited.append(("has a chart citing", line.visual.source))
            for verb, sid in cited:
                src = c.source(sid)
                if src is not None and src.kind == PRECEDENT_RECORD:
                    out.append(Failure(
                        "precedent",
                        f"{verb} {sid!r}, another government's record "
                        f"({PRECEDENT_RECORD!r}), which may be cited only "
                        f"as precedent, in a {BACKGROUND!r} section",
                        label, i))
    ids: Counter[str] = Counter()
    for label, sec in sc.labelled():
        for i, line in enumerate(sec.lines):
            if line.id is None:
                continue
            if not line.id.strip():
                out.append(Failure("questions", "has an empty 'id'", label, i))
            ids[line.id] += 1
    for lid, n in ids.items():
        if n > 1 and lid.strip():
            out.append(Failure("questions",
                               f"line id {lid!r} is used by {n} lines; "
                               f"each line's id is its own"))
    for k, q in enumerate(sc.questions):
        def fail(msg):
            out.append(Failure("questions", f"question[{k}] {msg}"))

        if not isinstance(q.ask, str) or not q.ask.strip():
            fail("needs 'ask', the question in plain words")
        if q.unanswered not in (None, True):
            fail("'unanswered' may only be true; leave it out for a "
                 "question the script answers")
        refs = q.lines
        if refs is not None and (
                not isinstance(refs, list)
                or not all(isinstance(r, str) and r for r in refs)):
            fail("'lines' must be a list of line ids")
            refs = []
        if refs and q.unanswered is True:
            fail("names the lines that answer it and is marked unanswered; "
                 "it is one or the other")
        elif not refs and q.unanswered is not True:
            fail("is neither answered nor marked unanswered: give 'lines', "
                 "the ids of the lines that answer it, or "
                 "'unanswered = true' where no official source does "
                 "(STANDARD.md rule 10.1)")
        for r in refs or ():
            if r not in ids:
                fail(f"names line {r!r}, which no line in the script has "
                     f"as its 'id'")
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


def _illustration_problems(v: Visual) -> list[str]:
    """An `illustration`: a name in the library, whose file exists."""
    out = []
    _forbid(v, ("title", "source", "unit", "labels", "values", "figure",
                "items", "focus", "highlight"), out)
    out += _library_problems(v.name, "name")
    return out


STAMP_MAX = 24  # characters: a stamp is a few words, read at a glance


def _stamp_problems(v: Visual) -> list[str]:
    """An illustration's optional `stamp`: short words on one line,
    written across its top. No other visual has one."""
    if v.stamp is None or v.kind not in VISUAL_KINDS:
        return []
    if v.kind != "illustration":
        return [f"a {v.kind!r} visual may not have 'stamp'"]
    if not isinstance(v.stamp, str) or not v.stamp.strip():
        return ["'stamp' must be a non-empty string"]
    if "\n" in v.stamp:
        return ["'stamp' must be one line"]
    if len(v.stamp) > STAMP_MAX:
        return [f"'stamp' is {len(v.stamp)} characters, more than "
                f"{STAMP_MAX}"]
    return []


def _library_problems(name: object, key: str) -> list[str]:
    """`name`, given as `key`: an entry in the illustration library whose
    file exists."""
    if name is None:
        return [f"has no {key!r}"]
    if not isinstance(name, str) or not name:
        return [f"{key!r} must be a non-empty string"]
    entry = load_library().get(name)
    if entry is None:
        return [f"names {name!r}, which is not in "
                f"film/illustrations/illustrations.toml"]
    if not entry.path.is_file():
        return [f"names {name!r}, whose file {entry.file!r} does not exist"]
    return []


def _timeline_problems(v: Visual) -> list[str]:
    out = []
    _forbid(v, ("title", "unit", "values", "figure", "name"), out)
    labels_ok = _string_list(v, "labels", out)
    items_ok = _string_list(v, "items", out)
    if labels_ok and items_ok:
        if len(v.labels) != len(v.items):
            out.append(f"has {len(v.labels)} labels but {len(v.items)} "
                       f"items")
        elif len(v.labels) < 2:
            out.append("a 'timeline' needs at least 2 entries")
    return out


def _list_problems(v: Visual) -> list[str]:
    """A `list`: a checklist of `items`, at least 1. No `title` or
    `labels`: it has no dates to carry a `timeline`'s date column."""
    out = []
    _forbid(v, ("title", "unit", "labels", "values", "figure", "name"), out)
    if _string_list(v, "items", out) and len(v.items) < 1:
        out.append("a 'list' needs at least 1 item")
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


def card_text(card: Card) -> str:
    """Everything the card shows that a `page` visual may click: its quoted
    fields, one per line."""
    return "\n".join(v for _, v in card.quoted() if isinstance(v, str))


def _page_problems(c: Contest, line: Line, v: Visual) -> list[str]:
    """A `page`: the script's card, its source cited by the line, and an
    optional `focus` phrase found on the card."""
    card = c.script.card
    if card is None:
        return ["needs a [card] table in script.toml"]
    out = []
    _forbid(v, ("title", "unit", "labels", "values", "figure", "items",
                "name"), out)
    out += _source_problems(c, line, v)
    if isinstance(v.source, str) and v.source != card.source:
        out.append(f"cites {v.source!r}, but the card quotes "
                   f"{card.source!r}")
    if v.focus is not None:
        if not isinstance(v.focus, str) or not v.focus.strip():
            out.append("'focus' must be a non-empty string")
        elif v.focus not in card_text(card):
            out.append(f"focus {v.focus!r} does not occur in the card's "
                       f"text")
    if v.highlight is not None:
        if v.focus is not None:
            out.append("has both 'focus' and 'highlight': a line clicks a "
                       "term or highlights phrases, not both")
        if (not isinstance(v.highlight, list) or not v.highlight
                or not all(isinstance(x, str) and x.strip()
                           for x in v.highlight)):
            out.append("'highlight' must be a non-empty list of non-empty "
                       "strings")
        else:
            for phrase in v.highlight:
                if phrase not in card_text(card):
                    out.append(f"highlight {phrase!r} does not occur in the "
                               f"card's text")
    return out


def _choices_visual_problems(c: Contest, line: Line, v: Visual) -> list[str]:
    """A `choices` visual: one page of a choice question's grid, citing
    the source its options are quoted from. Where it may appear, and how
    many, is check_choices's."""
    if c.script.choices is None:
        return ["needs a [choices] table in script.toml"]
    out = []
    _forbid(v, ("title", "unit", "labels", "values", "figure", "items",
                "name", "focus", "highlight"), out)
    out += _source_problems(c, line, v)
    want = c.script.choices.source
    if isinstance(v.source, str) and isinstance(want, str) \
            and v.source != want:
        out.append(f"cites {v.source!r}, but the choices are quoted from "
                   f"{want!r}")
    return out


def _visual_problems(c: Contest, line: Line, v: Visual) -> list[str]:
    """Everything wrong with visual `v` on `line`, per
    docs/SCRIPT-FORMAT.md."""
    if v.kind is None:
        return ["has no 'kind'"]
    if v.kind in REMOVED_KINDS:
        return ["only shows text, and the centre of the frame is for "
                "pictures: use an 'illustration' or a chart instead"]
    if v.kind not in VISUAL_KINDS:
        if isinstance(v.kind, str) and v.kind:
            return [f"kind {v.kind!r} is not one of "
                    f"{', '.join(VISUAL_KINDS)}"]
        return ["'kind' must be a non-empty string"]

    if v.kind == "illustration":  # no source of its own: the line cites
        return _illustration_problems(v)
    if v.kind == "page":
        return _page_problems(c, line, v)
    if v.kind == "choices":
        return _choices_visual_problems(c, line, v)
    for key in ("focus", "highlight"):
        if getattr(v, key) is not None:
            return [f"a {v.kind!r} visual may not have {key!r}"]
    out = []
    if v.kind in CHART_KINDS:
        if v.title is None:
            out.append("has no 'title'")
        elif not isinstance(v.title, str) or not v.title:
            out.append("'title' must be a non-empty string")
    out += _source_problems(c, line, v)
    if v.kind == "timeline":
        return out + _timeline_problems(v)
    if v.kind == "list":
        return out + _list_problems(v)

    if v.kind == "figure":
        if v.figure is None:
            out.append("a 'figure' chart has no 'figure'")
        elif not isinstance(v.figure, str) or not v.figure:
            out.append("'figure' must be a non-empty string")
        for key in ("labels", "values", "unit", "items", "name"):
            if getattr(v, key) is not None:
                out.append(f"a 'figure' chart may not have {key!r}")
        return out

    if v.figure is not None:
        out.append(f"a {v.kind!r} chart may not have 'figure'")
    _forbid(v, ("items", "name"), out)
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
    """Every visual is well formed, and every one but an illustration
    cites one of its line's sources (docs/SCRIPT-FORMAT.md; STANDARD.md
    7.1)."""
    out = []
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            if line.visual is None:
                continue
            kind = line.visual.kind
            what = ("chart" if kind in CHART_KINDS
                    or kind not in (*VISUAL_KINDS, *REMOVED_KINDS)
                    else f"{kind!r} visual")
            for msg in (_visual_problems(c, line, line.visual)
                        + _stamp_problems(line.visual)):
                out.append(Failure("visual", f"{what} {msg}", label, i))
    return out


def _printed_values(v: Visual) -> list:
    """The values a chart prints beside its marks: each bar's and each
    share's, and a series' last (its axis prints round steps, not data)."""
    if not isinstance(v.values, list) or not v.values or \
            not all(_is_number(x) for x in v.values):
        return []  # check_visuals reports it
    if v.kind in ("bars", "share"):
        return list(v.values)
    if v.kind == "series":
        return [v.values[-1]]
    return []


def _rounded(value: float, places: int) -> Decimal:
    """`value` rounded half up to `places` decimals, as a person rounds
    the figure written in the script (33.635 to one place is 33.6)."""
    return Decimal(repr(float(value))).quantize(
        Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _significant(figure: str) -> int:
    """How many significant digits a figure is written with: "33.6" 3,
    "0.5" 1, "1,500" 4."""
    return len(figure.replace(",", "").replace(".", "").lstrip("0"))


def check_chart_precision(c: Contest) -> list[Failure]:
    """A chart and its line's narration state a quantity at one precision:
    a value the chart prints (as film/measure.py does, ballotreels.printed)
    must not differ from a figure its own line says that it rounds to at
    the line's precision. Butte County's Measure Q printed 33.64 while its
    line said "33.6 million", and the value was fixed by hand. A printed
    value the line says exactly passes, and so does one the line does not
    say at all: a chart often shows figures the voice leaves out.

    A figure the chart prints exactly for one value is that value's, not a
    rounding of its neighbour's ("from 1 percent ... to 3 percent" over
    bars of 1 to 3 by halves), and a figure of one significant digit is
    too coarse to call the same figure ("Proposition 1" over 1.25)."""
    out = []
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            if line.visual is None:
                continue
            values = _printed_values(line.visual)
            shown = {v: Decimal(number(v).replace(",", "").lstrip("-"))
                     for v in values}
            said = [(f, Decimal(f.replace(",", "")))
                    for f in spoken.figures(line.text)]
            loose = [(f, n) for f, n in said
                     if n not in shown.values() and _significant(f) >= 2]
            for value in values:
                if any(n == shown[value] for _, n in said):
                    continue
                for f, n in loose:
                    places = max(0, -n.as_tuple().exponent)
                    if _rounded(abs(value), places) != n:
                        continue
                    printed = with_unit(value, line.visual.unit)
                    if places <= 2:
                        why = (f"the same figure rounded: the chart and the "
                               f"voice must state it alike; make the value "
                               f"{f.replace(',', '')}")
                    else:
                        why = ("which the chart, printing at most two "
                               "decimals (ballotreels.printed.number), "
                               "cannot show as said: the chart and the voice "
                               "must state it alike")
                    out.append(Failure(
                        "chart-precision",
                        f"the chart prints the value {value!r} as "
                        f"{printed!r}, but the line says {f!r}, {why}",
                        label, i))
                    break
    return out


_STRIP = re.compile(r"(?is)<(script|style)\b.*?</\1\s*>|<!--.*?-->|<[^>]*>")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+(?=[.,:;!?)\]])")


def plain_text(raw: str) -> str:
    """An archived page's text as a reader sees it, for the verbatim check:
    markup (and script and style contents) stripped, entities decoded,
    whitespace collapsed, and no space before punctuation. Quotes and case
    are kept as they are."""
    s = html.unescape(_STRIP.sub(" ", raw))
    return _normalise(s)


def _normalise(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return _SPACE_BEFORE_PUNCT.sub("", s)


# A digit "1" printed for a letter "l" at the end of a word, as Alabama's
# Fair Ballot Commission statement for Amendment 2 prints "potentia1"
# (the ballot itself prints "potential"). A card may quote the word as
# the ballot spells it; everything else stays verbatim.
_ONE_FOR_L = re.compile(r"(?<=[a-z])1(?![0-9A-Za-z])")


# The Latin ligatures a PDF's text may hold where the page prints two or
# three letters as one glyph (Lake County's Voter's Pamphlet sets
# "Uniﬁed" in Middletown Unified Measure C's question). A card quotes the
# letters as printed.
_LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
                            "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})


def _unligatured(archived: str) -> str:
    """`archived` with each Latin ligature written as its letters."""
    return archived.translate(_LIGATURES)


def _digit_one_read_as_l(archived: str) -> str:
    return _ONE_FOR_L.sub("l", archived)


class UnreadableSource(Exception):
    """An archived source whose text cannot be extracted here."""


@lru_cache(maxsize=8)
def _archived_text(path: Path) -> str:
    """An archived source's text, for the verbatim check: a page's
    plain_text, or a PDF's text as poppler's pdftotext extracts it,
    whitespace collapsed alike."""
    if path.suffix.lower() != ".pdf":
        return plain_text(path.read_text(encoding="utf-8", errors="replace"))
    return _normalise(_pdftotext(path))


@lru_cache(maxsize=8)
def _archived_blocks(path: Path) -> tuple[str, ...]:
    """An archived source's text as the blocks pdftotext separates with a
    blank line (a column's run of lines, a paragraph), each whitespace
    collapsed; a page's plain_text is one block."""
    if path.suffix.lower() != ".pdf":
        return (_archived_text(path),)
    blocks = (_normalise(b) for b in re.split(r"\n\s*\n", _pdftotext(path)))
    return tuple(b for b in blocks if b)


@lru_cache(maxsize=8)
def _pdftotext(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise UnreadableSource("pdftotext (poppler) is not installed")
    try:
        out = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"],
                             capture_output=True, check=True, timeout=60)
    except (subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as e:
        raise UnreadableSource(f"pdftotext failed: {e}") from None
    return out.stdout.decode("utf-8", errors="replace")


_WHITESPACE = re.compile(r"\s+")


@lru_cache(maxsize=8)
def _raw_text(path: Path) -> str | None:
    """A PDF's text in the order it is printed (pdftotext -raw); None for
    a page, or where the PDF cannot be read."""
    if path.suffix.lower() != ".pdf" or shutil.which("pdftotext") is None:
        return None
    try:
        out = subprocess.run(["pdftotext", "-raw", "-enc", "UTF-8",
                              str(path), "-"],
                             capture_output=True, check=True, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return out.stdout.decode("utf-8", errors="replace")


@lru_cache(maxsize=8)
def _unspaced_raw_text(path: Path) -> str | None:
    """A PDF's text in the order it is printed (pdftotext -raw), every
    space removed; None for a page, or where the PDF cannot be read.

    A newspaper-style PDF set in narrow columns (Georgia's amendment
    booklet) defeats pdftotext's default reading order, which interleaves
    lines of neighbouring columns; -raw keeps each column whole but runs
    words together ("ShalltheConstitution"). A card quote that is not in
    the default text may instead be in this one, compared with all
    whitespace removed from both: the words and their order still match
    exactly."""
    raw = _raw_text(path)
    return None if raw is None else _WHITESPACE.sub("", raw)


def _in_raw_columns(value: str, path: Path) -> bool:
    """Whether `value` is in the PDF at `path` read column by column, as
    _unspaced_raw_text compares it."""
    raw = _unspaced_raw_text(path)
    return raw is not None and _WHITESPACE.sub("", value) in raw


# Alameda County's Composite Voter Information Guide sets much of its
# text in a font with no Unicode map, which pdftotext reads as glyph ids:
# each character 29 below the one printed ("PHDVXUH" for "measure", a
# control character \x03 for a space), a few ligatures and quotes as
# stray symbols, and parentheses not at all. These are the stray symbols.
_SHIFTED_SYMBOLS = {"³": "“", "´": "”", "¶": "’", "¿": "fi", "À": "fl",
                    "൵": "ff", "൶": "ffi"}
_SHIFTED_CONTROL = re.compile(r"[\x01-\x08\x0e-\x1f]")


def _unshift_line(line: str, beside: bool) -> str:
    """One line of pdftotext's text with its glyph-id words read back as
    printed. A word is shifted where it holds a control character or a
    stray symbol, or sits between two shifted spaces, or (with `beside`)
    beside one: "DQ" is "an" there, but a printed "II" may sit there too,
    so the text is read both ways. In a word that also has a lower-case letter (a printed word
    with shifted punctuation glued on), or a character no shifted word
    holds ("BONDS" would read back as "_lkap"), only the control
    characters and symbols are read back; printed punctuation ending a
    word stays as it is."""
    parts = re.split(r"(\x03| )", line)

    def beside_shifted_space(i: int, step: int) -> bool:
        j = i + step
        while 0 <= j < len(parts) and parts[j] in ("", " "):
            j += step
        return 0 <= j < len(parts) and parts[j] == "\x03"

    out = []
    for i, tok in enumerate(parts):
        if tok == "\x03":
            out.append(" ")
            continue
        shifted = tok not in ("", " ") and (
            _SHIFTED_CONTROL.search(tok) is not None
            or any(ch in _SHIFTED_SYMBOLS for ch in tok)
            or (beside_shifted_space(i, -1) and beside_shifted_space(i, 1))
            or (beside and (beside_shifted_space(i, -1)
                            or beside_shifted_space(i, 1))))
        if not shifted:
            out.append(tok)
            continue
        whole = re.search(r"[a-z]", tok) is None \
            and not re.search(r"[A-C\x5e-\x7f]", tok)
        ending = len(tok) - len(tok.rstrip(".,;:!?"))
        for k, ch in enumerate(tok):
            o = ord(ch)
            if ch in _SHIFTED_SYMBOLS:
                out.append(_SHIFTED_SYMBOLS[ch])
            elif _SHIFTED_CONTROL.match(ch) or (
                    whole and 0x21 <= o <= 0x5f and k < len(tok) - ending):
                out.append(chr(o + 29))
            else:
                out.append(ch)
    return "".join(out)


@lru_cache(maxsize=8)
def _unshifted_text(path: Path) -> str | None:
    """A PDF's text with its glyph-id lines read back as printed, both ways
    _unshift_line reads them, one after the other, each whitespace
    collapsed and parentheses dropped (the font prints them with no text);
    None for a page, or a PDF with no such lines."""
    if path.suffix.lower() != ".pdf":
        return None
    try:
        text = _pdftotext(path)
    except UnreadableSource:
        return None
    if _SHIFTED_CONTROL.search(text) is None:
        return None
    reads = ("\n".join(_unshift_line(l, beside)
                       if _SHIFTED_CONTROL.search(l) else l
                       for l in text.split("\n"))
             for beside in (True, False))
    return "\n\n".join(_normalise(re.sub(r"[()]", " ", r)) for r in reads)


# the ballot's vote boxes beside the question, which pdftotext reads into
# its lines
_BOX_LABELS = re.compile(r" (?:BONDS|YES|NO)(?= )")


def _unshifted_form(s: str) -> str:
    """`s` as _in_unshifted compares it: parentheses and the vote boxes'
    labels dropped, every hyphen, with the spaces around it, removed
    (pdftotext drops a printed hyphen at a line's end), and the space
    after a slash ending a line ("paramedics/ fire"), and apostrophes,
    which the font drops after a plural ("Councilmembers' right")."""
    s = _normalise(re.sub(r"[()]", " ", s))
    s = re.sub(r"['’]", "", s)
    s = _BOX_LABELS.sub("", f" {s} ").strip()
    return re.sub(r"\s*-\s*", "", re.sub(r"/ ", "/", s))


def _in_unshifted(value: str, path: Path) -> bool:
    """Whether a card quote is in the PDF at `path` read back as
    _unshifted_text reads it, both compared as _unshifted_form gives
    them."""
    text = _unshifted_text(path)
    return text is not None and _unshifted_form(value) in _unshifted_form(text)


def highlight_counts(c: Contest) -> tuple[int, int]:
    """How many highlighted occurrences, over the whole script, fall in the
    card's YES box and in its NO box: each well-formed `highlight` phrase
    counts once for every time it occurs in each box."""
    card = c.script.card
    yes = card.yes if card is not None and isinstance(card.yes, str) else ""
    no = card.no if card is not None and isinstance(card.no, str) else ""
    n_yes = n_no = 0
    for sec in c.script.sections:
        for line in sec.lines:
            v = line.visual
            if v is None or v.kind != "page" or not isinstance(v.highlight,
                                                               list):
                continue
            for phrase in v.highlight:
                if isinstance(phrase, str) and phrase:
                    n_yes += yes.count(phrase)
                    n_no += no.count(phrase)
    return n_yes, n_no


def check_highlight_balance(c: Contest) -> list[Failure]:
    """STANDARD.md 7.4: the page's YES and NO boxes are highlighted alike:
    as many highlighted occurrences in one as in the other, over the whole
    script."""
    n_yes, n_no = highlight_counts(c)
    if n_yes == n_no:
        return []
    return [Failure("highlight-balance",
                    f"highlights fall {n_yes} times in the card's YES box "
                    f"and {n_no} times in its NO box; they must be equal")]


def check_ballot(c: Contest) -> list[Failure]:
    """A measure's state has its ballot's wording in ballotreels.ballots,
    so the film never borrows another state's."""
    if c.kind != "measure" or ballot_for(c.division) is not None:
        return []
    return [Failure("ballot",
                    f"no ballot wording for the state of {c.division!r}; "
                    f"add it to ballotreels/ballots.py")]


def check_card(c: Contest) -> list[Failure]:
    """The `[card]`, if any: every required key present, `yes` and `no`
    together or neither, a badge word from the contest's title, a source
    of the kind the state's card quotes, and each quoted field verbatim in
    that source's archived text (docs/SCRIPT-FORMAT.md)."""
    card = c.script.card
    if card is None:
        return []
    out = []

    def fail(msg):
        out.append(Failure("card", msg))

    for key in CARD_KEYS:
        value = getattr(card, key)
        if value is None:
            if key not in Card.OPTIONAL:
                fail(f"has no {key!r}")
        elif not isinstance(value, str) or not value.strip():
            fail(f"{key!r} must be a non-empty string")
    if (card.yes is None) != (card.no is None):
        have, lack = ("yes", "no") if card.no is None else ("no", "yes")
        fail(f"has {have!r} but no {lack!r}: the two votes' meanings come "
             f"together or not at all")
    ballot: Ballot | None = ballot_for(c.division)
    if ballot is None:
        return out  # check_ballot reports it
    if card.fiscal is not None and ballot.fiscal_label is None:
        fail("has a 'fiscal' quote, but the state's guide prints no "
             "fiscal statement to quote")
    if isinstance(card.number, str) and card.number.strip() \
            and badge(ballot, c.title, card.number) is None:
        fail(f"the contest title {c.title!r} has no designation word just "
             f"before the number {card.number!r}, for the card's badge")
    if not isinstance(card.source, str) or not card.source:
        return out
    src = c.source(card.source)
    if src is None:
        fail(f"source {card.source!r} is not in sources.toml")
        return out
    if src.kind != ballot.card_source_kind:
        fail(f"source {card.source!r} is of kind {src.kind!r}; a card "
             f"quotes the measure's page in the "
             f"{guide_of(ballot, c.id)}, a source "
             f"of kind {ballot.card_source_kind!r}")
        return out
    path = (c.path / src.file).resolve()
    if not path.is_relative_to(c.path.resolve()) or not path.is_file():
        return out  # check_sources reports it
    try:
        archived = _archived_text(path)
        blocks = _archived_blocks(path) if ballot.card_column_breaks \
            else None
    except UnreadableSource as e:
        fail(f"cannot read source {card.source!r} ({src.file}) to check "
             f"the card's quotes: {e}")
        return out
    strays = ballot.card_strays.get(c.id, ())
    if strays:
        archived = _without_strays(archived, strays)
    for key, value in card.quoted():
        # a hyphen may be missing where pdftotext joined a word hyphenated
        # across a line break ("eighty-" / "two" -> "eightytwo")
        if isinstance(value, str) and value.strip() \
                and not _in_text(value, archived) \
                and not _in_raw_columns(value, path) \
                and not _in_unshifted(value, path) \
                and not _card_quote_in(value, archived, blocks) \
                and _normalise(value) not in _unligatured(archived) \
                and _normalise(value) not in _digit_one_read_as_l(archived):
            fail(f"{key!r} does not appear verbatim in source "
                 f"{card.source!r} ({src.file})")
    return out


def _without_strays(archived: str, strays: tuple[str, ...]) -> str:
    """`archived` with each of `strays` (Ballot.card_strays) dropped
    wherever it stands as whole words, whitespace collapsed again."""
    for stray in strays:
        archived = re.sub(r"(?<!\S)" + re.escape(stray) + r"(?!\S)", " ",
                          archived)
    return _normalise(archived)


CARD_PIECE_MIN_WORDS = 6


def _card_quote_in(value: str, archived: str,
                   blocks: tuple[str, ...] | None) -> bool:
    """Whether a card quote occurs in its source's archived text: verbatim,
    whitespace collapsed. Where the state's card source is set in columns
    that pdftotext reads out of order (Ballot.card_column_breaks), `blocks`
    is that text in pdftotext's blank-line-separated blocks; a hyphen may
    then be missing, as for a choice's label, and the quote may run across
    one column break: two pieces, each of at least CARD_PIECE_MIN_WORDS
    words, the first ending one block and the second starting another. A
    piece found only mid-block is no column break, so a quote stitched
    from two places on the sheet still fails."""
    want = _normalise(value)
    if want in archived:
        return True
    if blocks is None:
        return False
    if _in_text(want, archived):
        return True
    words = want.split(" ")
    n = CARD_PIECE_MIN_WORDS
    for i in range(n, len(words) - n + 1):
        head = re.compile(_hyphen_optional(" ".join(words[:i])) + r"\Z")
        tail = re.compile(_hyphen_optional(" ".join(words[i:])))
        if any(head.search(b) for b in blocks) \
                and any(tail.match(b) for b in blocks):
            return True
    return False


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
    if sc.choices is not None:
        t = CHOICE_TEMPLATES.get(sc.template, {}).get(sc.template_version)
        if t is None:
            return [Failure("template",
                            f"{sc.template} v{sc.template_version} has no "
                            f"choice question: a [choices] table needs "
                            f"{_choice_versions()}")]
    out = []
    got = tuple(s.id for s in sc.sections)
    if not _fits(got, t):
        want = ", ".join(f"{sid}*" if sid in t.repeated else sid
                         for sid in t.sections)
        note = " (* zero or more)" if t.repeated else ""
        out.append(Failure("template",
                           f"sections are {', '.join(got) or '(none)'}; "
                           f"{'a choice question under ' if sc.choices is not None else ''}"
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


def _choice_versions() -> str:
    return " or ".join(f"{name} v{v}" for name, vs in CHOICE_TEMPLATES.items()
                       for v in vs)


def check_side_headings(c: Contest) -> list[Failure]:
    """A side's heading uses only the ballot's own word for its choice
    ("Why some vote yes" in California, "Why some vote for" in Utah):
    never the other side's word, nor another state's words for either
    (ballotreels.ballots). A heading may name no choice at all."""
    ballot = ballot_for(c.division)
    if ballot is None:
        return []  # check_ballot reports it
    every = {w.lower() for b in BALLOTS.values() for w in b.choices}
    out = []
    for label, sec in c.script.labelled():
        if sec.side not in ("yes", "no"):
            continue
        own = ballot.choices[0 if sec.side == "yes" else 1]
        # the side's own word set aside first, so the words inside a
        # choice of two ("Yes/For" in Colorado) are not taken for others
        heading = re.sub(rf"\b{re.escape(own)}\b", " ", sec.heading,
                         flags=re.IGNORECASE)
        for word in sorted(every - {own.lower()}):
            if re.search(rf"\b{re.escape(word)}\b", heading,
                         re.IGNORECASE):
                out.append(Failure(
                    "side-heading",
                    f"heading {sec.heading!r} says {word!r}; the ballot's "
                    f"word for this side is {own!r}", label))
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
    has visuals of the same kinds (as many of each). And since both sides
    share one slide (film/measure.py's sides slide), whose two blocks hold
    each side's checklist and nothing else, the only visual a side may
    have is one 'list': anything else would pass here and then never be
    drawn."""
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

    def show(counts: Counter) -> str:
        return ", ".join(sorted(counts.elements())) or "none"

    out = []
    for label, sec in (yes[0], no[0]):
        lists = 0
        for i, line in enumerate(sec.lines):
            if line.visual is None:
                continue
            kind = line.visual.kind
            if kind == "list":
                lists += 1
            if kind != "list" or lists > 1:
                out.append(Failure(
                    "side-visual",
                    f"a side section may have one 'list' visual and no "
                    f"other: both sides share one slide, which draws "
                    f"nothing else (this is a {kind!r}"
                    f"{' after the first' if kind == 'list' else ''})",
                    label, i))
            elif have["yes"] != have["no"]:
                out.append(Failure(
                    "side-visual",
                    f"a visual in a side section needs visuals of the same "
                    f"kinds on both sides: yes has {show(have['yes'])}, "
                    f"no has {show(have['no'])}",
                    label, i))
    return out


def check_side_list_items(c: Contest) -> list[Failure]:
    """STANDARD.md 7.3: when a side section has a 'list' visual, the other
    side's must have the same number of items in all (check_side_visuals
    already requires both sides to have a 'list' or neither). A side that
    filed no argument (filed = false) lists only that fact, so the counts
    are not compared."""
    by_side: dict[str, list[Section]] = {}
    for sec in c.script.sections:
        if sec.side is not None:
            by_side.setdefault(sec.side, []).append(sec)
    yes, no = by_side.get("yes", []), by_side.get("no", [])
    if len(yes) != 1 or len(no) != 1:
        return []  # a template failure; nothing to compare
    if not (yes[0].filed and no[0].filed):
        return []

    def count(sec: Section) -> int:
        return sum(len(ln.visual.items) for ln in sec.lines
                   if ln.visual is not None and ln.visual.kind == "list"
                   and isinstance(ln.visual.items, list))

    n_yes, n_no = count(yes[0]), count(no[0])
    if n_yes == n_no:
        return []
    return [Failure("side-list-items",
                    f"the yes section's 'list' has {n_yes} items in all; "
                    f"the no section's has {n_no}; they must match")]


# The most the two sides' estimated spoken durations may differ before
# narration: check_airtime pads up to narration.SIDE_PAD_CAP (2 s) after
# it, and spoken.seconds's estimate of the difference is off by 0.55 s
# RMS, so the margin is 0.9 s. It flags Montana CI-132's first draft
# (1.31 s estimated, 2.1 s when narrated), and 3 of the 31 committed pairs
# with both sides filed, if their sides were narrated again (an edit
# elsewhere re-speaks no side, so is not estimated): I-194 (1.14 s
# narrated), Arizona 142 (1.15 s) and CI-132 as committed (1.74 s, the
# nearest of all to the cap).
SPOKEN_PARITY_LIMIT = 1.1


def check_spoken_parity(c: Contest,
                        pieces: tuple[narration.NarrationLine, ...] | None = None
                        ) -> list[Failure]:
    """STANDARD.md 2.2, before narration: the two sides' estimated spoken
    durations (spoken.seconds: numbers, money and symbols said in full)
    differ by at most SPOKEN_PARITY_LIMIT, so the narration will pass
    check_airtime. Equal word counts are not enough: "nearly $90,000" is
    two words, said as five. A side that filed no argument is exempt, as
    from check_airtime.

    `pieces` is what `say` would synthesise afresh (default: everything);
    check_contest passes narration.unreused_phrases. When none of it is in
    a side section, both sides are said exactly as they were when they
    passed check_airtime, so there is nothing to estimate. Otherwise both
    sides are estimated whole, recorded phrases too: the estimate's error
    is mostly the take's pace, which cancels only between two estimates,
    so a recorded side against an estimated one would miss CI-132's
    draft."""
    by_side: dict[str, list[tuple[str, Section]]] = {}
    for label, sec in c.script.labelled():
        if sec.side is not None:
            by_side.setdefault(sec.side, []).append((label, sec))
    yes, no = by_side.get("yes", []), by_side.get("no", [])
    if len(yes) != 1 or len(no) != 1:
        return []  # a template failure; nothing to compare
    if not (yes[0][1].filed and no[0][1].filed):
        return []
    if pieces is not None and not any(p.section in (yes[0][0], no[0][0])
                                      for p in pieces):
        return []
    est = {label: spoken.seconds("\n".join(ln.text for ln in sec.lines))
           for label, sec in (yes[0], no[0])}
    (la, a), (lb, b) = est.items()
    if abs(a - b) <= SPOKEN_PARITY_LIMIT:
        return []
    longer = la if a > b else lb
    said = [f"{label}: {spoken.spoken_text(ln.text)!r}"
            for label, sec in (yes[0], no[0]) for ln in sec.lines
            if spoken.spoken_text(ln.text) != " ".join(ln.text.split())]
    return [Failure(
        "spoken-parity",
        f"the sides' estimated spoken durations differ by {abs(a - b):.2f}s "
        f"({la}={a:.2f}s, {lb}={b:.2f}s), more than the "
        f"{SPOKEN_PARITY_LIMIT:.2f}s allowed before narration (the airtime "
        f"check pads at most {narration.SIDE_PAD_CAP:.0f}s, and this "
        f"estimate can be off by half a second); shorten {longer} or "
        f"lengthen the other, counting numbers as said"
        + (f" ({'; '.join(said)})" if said else ""))]


def check_airtime(c: Contest) -> list[Failure]:
    """STANDARD.md 2.2/4.1: the two sides spend exactly the same time on
    screen. The shorter side is padded with silence at its end
    (narration.side_pad) to match the longer, so this fails only when
    the raw gap is too big to pad invisibly (more than
    narration.SIDE_PAD_CAP: a real imbalance in the script, not TTS
    noise), or when the padded layout's two side sections still come out
    different lengths, which would mean a bug in the padding itself.

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
    gap = abs(dur_a - dur_b)
    # a side that filed nothing says only that, so its shortness is not an
    # imbalance in the script: pad it whatever the gap
    filed = all(s.filed for s in c.script.sections if s.side is not None)
    if filed and gap > narration.SIDE_PAD_CAP:
        return [Failure("airtime",
                        f"side spoken durations differ by {gap:.1f}s, more "
                        f"than the {narration.SIDE_PAD_CAP:.0f}s this check "
                        f"pads automatically: {side_a}={dur_a:.1f}s, "
                        f"{side_b}={dur_b:.1f}s")]
    try:
        board = storyboard.layout(c, 0.0)
    except ImportError:
        return []
    except narration.NarrationError:
        return []
    except KeyError:
        return []
    by_side = {sb.section.side: sb for sb in board.sections
              if sb.section.side is not None}
    if len(by_side) != 2:
        return []
    beat_a, beat_b = by_side.values()
    label_a, label_b = beat_a.label, beat_b.label
    frames_a, frames_b = beat_a.end - beat_a.start, beat_b.end - beat_b.start
    # narration.side_pad sizes the pad in whole frames from these same
    # section lengths, so any difference at all is a bug in the padding
    if frames_a == frames_b:
        return []
    on_a, on_b = frames_a / board.fps, frames_b / board.fps
    return [Failure("airtime",
                    f"side on-screen durations differ by "
                    f"{abs(on_a - on_b):.2f}s after padding, which should "
                    f"not happen: {label_a}={on_a:.2f}s, "
                    f"{label_b}={on_b:.2f}s")]


_PAREN = re.compile(r"\s*\([^()]*\)")


def spoken_forms(label: str) -> set[str]:
    """The ways a narration may name an option printed as `label`: as
    printed, or with any of its parenthesised parts left out (a calibre, a
    code: words that read badly aloud), whitespace collapsed."""
    groups = list(_PAREN.finditer(label))
    out = set()
    for mask in range(1 << len(groups)):
        kept, pos = [], 0
        for k, m in enumerate(groups):
            kept.append(label[pos:m.start()])
            if not mask >> k & 1:
                kept.append(m.group(0))
            pos = m.end()
        kept.append(label[pos:])
        out.add(_normalise("".join(kept)))
    return out


def _letter_series(letters: list[str]) -> bool:
    """Whether `letters`, each stripped to its letters and digits ("(a)" ->
    "a"), run on from the first of a series: a, b, c; A, B, C; or 1, 2, 3."""
    cores = [re.sub(r"[^0-9A-Za-z]", "", x) for x in letters]
    if not cores or cores[0] not in ("a", "A", "1"):
        return False
    for i, core in enumerate(cores):
        if cores[0] == "1":
            if core != str(i + 1):
                return False
        elif len(core) != 1 or ord(core) != ord(cores[0]) + i:
            return False
    return True


def _in_text(phrase: str, archived: str) -> bool:
    """Whether `phrase` occurs in an archived source's text, compared as
    the card is (verbatim, whitespace collapsed), except that a hyphen in
    the phrase may be missing from the text: pdftotext joins a word
    hyphenated across a line break ("bolt-" / "action" -> "boltaction"),
    and drops a dash standing alone at a line's end with it ("$0.60 -" /
    "$1.50" -> "$0.60 $1.50")."""
    want = _normalise(phrase)
    if want in archived:
        return True
    if re.search(_hyphen_optional(want), archived) is not None:
        return True
    unspaced = want.replace(" - ", " ")
    return unspaced != want and \
        re.search(_hyphen_optional(unspaced), archived) is not None


def _hyphen_optional(phrase: str) -> str:
    """A regex for `phrase` with each of its hyphens optional."""
    return "-?".join(re.escape(p) for p in phrase.split("-"))


# A basis is compared looser than a card quote: a side's argument is
# often a PDF, whose text breaks words across lines ("con- sents",
# "social- media" -> "socialmedia"), prints ligatures ("ﬁ") and curly
# quotes, where the script types straight ones.
_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                         "“": '"', "”": '"', "„": '"', "‟": '"',
                         "\u00ad": None})
BASIS_MIN_WORDS = 6
# What a side's `basis` may quote: its official argument, or, where the
# state publishes none, a university guide's account of what the side
# says (STANDARD.md 1.2; check_university_guide keeps it to that).
ARGUMENT_KINDS = frozenset({"official-argument", UNIVERSITY_GUIDE})


def _loose(s: str) -> str:
    """`s` for a basis comparison: ligatures and other compatibility
    characters unfolded (NFKC), quotes straightened, soft hyphens dropped,
    whitespace collapsed, and every hyphen or dash, with the spaces
    around it, removed, so a word hyphenated across a line matches it
    whole and a compound split at a hyphen matches it joined."""
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES)
    s = re.sub(r"\s*[-‐‑–—]\s*", "", _normalise(s))
    return s


@lru_cache(maxsize=8)
def _loose_archived(path: Path) -> str:
    """`path`'s text for a basis comparison: as pdftotext reads it, then
    any glyph-id lines read back, then, for a PDF, its text in printed
    order (pdftotext -raw), since a scan's doubled text layer (Tulelake
    Multi-County FPD's argument for Measure I) can defeat the default
    reading order, which interleaves the copies word by word."""
    parts = [_archived_text(path), _unshifted_text(path), _raw_text(path)]
    return " ".join(_loose(p) for p in parts if p is not None)


def check_side_basis(c: Contest, required: bool) -> list[Failure]:
    """docs/SCRIPT-FORMAT.md's `basis`: each entry of a line's `basis` is
    a passage of at least BASIS_MIN_WORDS words that appears verbatim in
    an `official-argument` source the line cites (or a `university-guide`,
    where the state has no official arguments), so a reader can hold the
    line against the point it distils (SCRIPT-RECIPE.md, "Sides"). Only a
    side's lines may have one. With `required` (a script still to be
    narrated), every line of a side that filed an argument must have
    one."""
    sides = Counter(sec.side for sec in c.script.sections
                    if sec.side is not None)
    if sides != Counter({"yes": 1, "no": 1}):
        return []  # a template failure; which lines are a side's is unclear
    out = []
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            def fail(msg):
                out.append(Failure("side-basis", msg, label, i))

            if sec.side is None:
                if line.basis is not None:
                    fail("has a 'basis', but only a side's lines distil "
                         "an argument")
                continue
            if line.basis is None:
                if required and sec.filed and not line.connective:
                    fail("has no 'basis': quote the passage of the side's "
                         "official argument this line distils (needed "
                         "until the script is narrated)")
                continue
            if not line.basis:
                fail("'basis' is empty: quote at least one passage")
                continue
            args = [s for sid in line.sources or ()
                    if (s := c.source(sid)) is not None
                    and s.kind in ARGUMENT_KINDS]
            if not args:
                fail("has a 'basis' but cites no 'official-argument' source "
                     "(or, where the state has none, 'university-guide' "
                     "source) to quote it from")
                continue
            texts = []
            for src in args:
                path = (c.path / src.file).resolve()
                if not path.is_relative_to(c.path.resolve()) \
                        or not path.is_file():
                    continue  # check_sources reports it
                try:
                    texts.append(_loose_archived(path))
                except UnreadableSource as e:
                    fail(f"cannot read source {src.id!r} ({src.file}) to "
                         f"check the basis: {e}")
            if not texts:
                continue
            for passage in line.basis:
                if len(passage.split()) < BASIS_MIN_WORDS:
                    fail(f"basis {passage!r} is under {BASIS_MIN_WORDS} "
                         f"words: quote enough to show the point")
                elif not any(_loose(passage) in t for t in texts):
                    ids = ", ".join(repr(s.id) for s in args)
                    fail(f"basis {passage!r} does not appear verbatim in "
                         f"the argument it cites ({ids})")
    return out


# STANDARD.md section 9: a script names a person or organisation only as
# a line's declared `names`, each from a record of an allowed kind.
NAMING = "naming"
# A word, with any possessive or hyphenated part: "Utah's", "René", "CI-132".
_WORD = re.compile(r"[^\W\d_][\w'’-]*")
_POSSESSIVE = re.compile(r"['’]s?$")
_SENTENCE_BREAK = re.compile(r"[.!?:;]")
# Words a sentence may open with, capitalised only for that.
_OPENERS = frozenset("""a an the in on at for from to under after before if
but and so then today each most only other those they it this that these
what when why how""".split())


def _bare(word: str) -> str:
    """`word` without a possessive ending: "Utah's" -> "Utah"."""
    return _POSSESSIVE.sub("", word)


def _official_words(c: Contest) -> set[str]:
    """The capitalised words of the contest's own official wording: its
    title, its card, its sources' publishers and credits, its headings and
    its choices' labels. A run of these names the measure or its sources,
    not a person."""
    texts = [c.title, *(s.publisher for s in c.sources),
             *(s.credit or "" for s in c.sources),
             *(sec.heading for sec in c.script.sections)]
    if c.script.card is not None:
        texts.append(card_text(c.script.card))
    if c.script.choices is not None:
        texts += [x for ch in c.script.choices.choices
                  for x in (ch.label, ch.spoken) if isinstance(x, str)]
    return {_bare(m.group(0)) for t in texts for m in _WORD.finditer(t)
            if m.group(0)[0].isupper()}


def proper_runs(text: str) -> list[tuple[int, list[tuple[str, bool]]]]:
    """Each run of two or more capitalised words in `text`, separated only
    by spaces, as (offset, [(word without possessive, opens a sentence)])."""
    runs: list[tuple[int, list[tuple[str, bool]]]] = []
    run: list[tuple[str, bool]] = []
    start = prev_end = 0
    for m in _WORD.finditer(text):
        gap = text[prev_end:m.start()]
        opens = prev_end == 0 or _SENTENCE_BREAK.search(gap) is not None
        if run and (gap.strip() or not m.group(0)[0].isupper()):
            if len(run) > 1:
                runs.append((start, run))
            run = []
        if m.group(0)[0].isupper():
            if not run:
                start = m.start()
            run.append((_bare(m.group(0)), opens))
        prev_end = m.end()
    if len(run) > 1:
        runs.append((start, run))
    return runs


def _undeclared(c: Contest, line: Line, known: set[str],
                lowered: set[str]) -> list[str]:
    """The runs of capitalised words in `line` that may be a name it does
    not declare: a run with a word that is neither a known word (the
    contest's official words, standard/proper-words.txt) nor a sentence's
    ordinary opening word."""
    text = line.text
    for n in line.names:
        if isinstance(n.name, str) and n.name:
            text = text.replace(n.name, "|")
    out = []
    for start, run in proper_runs(text):
        def ok(word, opens):
            return word in known or (opens and (word.lower() in _OPENERS
                                                or word.lower() in lowered))
        if not all(ok(w, o) for w, o in run):
            out.append(" ".join(w for w, _ in run))
    return out


def _unaccent(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(ch))


def _name_problems(c: Contest, line: Line, n) -> list[str]:
    """What is wrong with one declared name: its fields, its place in the
    line's text, and its source."""
    bad = [k for k in ("name", "role", "source")
           if not isinstance(getattr(n, k), str) or not getattr(n, k).strip()]
    if bad:
        return [f"a declared name needs a non-empty {', '.join(bad)}"]
    out = []
    if re.search(rf"(?<!\w){re.escape(n.name)}(?!\w)", line.text) is None:
        out.append(f"declares {n.name!r}, which the line does not say")
    if n.role not in line.text:
        out.append(f"declares {n.name!r} as {n.role!r}, but the line does "
                   f"not say that role")
    if n.source not in (line.sources or ()):
        out.append(f"{n.name!r} comes from {n.source!r}, which the line "
                   f"does not cite")
        return out
    src = c.source(n.source)
    if src is None:
        return out  # check_cited_sources_exist reports it
    if src.kind not in NAMING_KINDS:
        kinds = ", ".join(sorted(NAMING_KINDS))
        out.append(f"{n.name!r} comes from {src.id!r}, of kind {src.kind!r}; "
                   f"a name comes only from a record of kind {kinds} "
                   f"(STANDARD.md rule 9.1)")
        return out
    path = (c.path / src.file).resolve()
    if not path.is_relative_to(c.path.resolve()) or not path.is_file():
        return out  # check_sources reports it
    try:
        archived = _loose_archived(path)
    except UnreadableSource as e:
        return [*out, f"cannot read source {src.id!r} ({src.file}) to check "
                      f"{n.name!r}: {e}"]
    # accents folded: the narration writes "Rene" for a source's "René",
    # because the transcript check hears no accents (speakability.txt)
    if _unaccent(_loose(n.name)) not in _unaccent(archived):
        out.append(f"{n.name!r} does not appear verbatim in {src.id!r} "
                   f"({src.file})")
    return out


def check_naming(c: Contest, proper_words: frozenset[str] = frozenset()
                 ) -> list[Failure]:
    """STANDARD.md section 9, as docs/SCRIPT-FORMAT.md's `names`: every
    person or organisation a line says is declared on that line, with its
    role, from a source the line cites, of a kind the record allows, in
    which the name appears verbatim; names go only in a background or a
    side section, never in the opening line or the vote lines; and the two
    sides name as many as each other, where both filed. A name is found by
    a heuristic (_undeclared): a run of capitalised words not all known."""
    sc = c.script
    known = _official_words(c) | set(proper_words)
    lowered = {m.group(0) for sec in sc.sections for line in sec.lines
               for m in _WORD.finditer(line.text) if m.group(0).islower()}
    declared = {n.name for sec in sc.sections for line in sec.lines
                for n in line.names if isinstance(n.name, str) and n.name}
    try:  # a side section missing its `side` is check_template's
        side_ids = tuple(template_for(sc).sides)
    except KeyError:
        side_ids = ()
    out = []
    per_side: dict[str, list[tuple[str, Section]]] = {}
    for label, sec in sc.labelled():
        if sec.side is not None:
            per_side.setdefault(sec.side, []).append((label, sec))
        for i, line in enumerate(sec.lines):
            def fail(msg):
                out.append(Failure(NAMING, msg, label, i))

            for run in _undeclared(c, line, known, lowered):
                fail(f"says {run!r}, which may be a person's or an "
                     f"organisation's name: declare it in the line's "
                     f"'names' (STANDARD.md section 9), or, if it names no "
                     f"one, add its words to standard/proper-words.txt")
            for n in line.names:
                for msg in _name_problems(c, line, n):
                    fail(msg)
            opening = sec is sc.sections[0] and i == 0
            if opening or sec.id == "vote":
                where = "the opening line" if opening else "a vote line"
                said = sorted(d for d in declared
                              if re.search(rf"(?<!\w){re.escape(d)}(?!\w)",
                                           line.text))
                for d in said:
                    fail(f"names {d!r} in {where}; a name never goes there "
                         f"(STANDARD.md rule 9.5)")
            elif line.names and sec.side is None \
                    and sec.id not in (BACKGROUND, *side_ids):
                fail(f"names {', '.join(repr(n.name) for n in line.names)} "
                     f"in the {sec.id!r} section; a name goes only in a "
                     f"background section or a side's own (STANDARD.md "
                     f"rule 9.5)")
    yes, no = per_side.get("yes", []), per_side.get("no", [])
    if len(yes) == 1 and len(no) == 1 and yes[0][1].filed and no[0][1].filed:
        counts = {label: sum(len(line.names) for line in sec.lines)
                  for label, sec in (yes[0], no[0])}
        (la, a), (lb, b) = counts.items()
        if a != b:
            out.append(Failure(
                NAMING, f"the sides name different numbers of people or "
                        f"organisations ({la}={a}, {lb}={b}); each side's "
                        f"most prominent is named the same way, as many "
                        f"times (STANDARD.md rule 9.3)"))
    return out


def _occurrences(text: str, names: list[str]) -> list[tuple[int, int]]:
    """(position, option index) of every occurrence of each option's name
    in `text`, in text order; a name inside a longer option's name (say
    "Colt" in "Colt pistol") is not counted for the shorter one."""
    found = []
    taken = [False] * len(text)
    for i in sorted(range(len(names)), key=lambda i: -len(names[i])):
        name = names[i]
        if not name:
            continue
        k = text.find(name)
        while k >= 0:
            if not any(taken[k:k + len(name)]):
                found.append((k, i))
                for j in range(k, k + len(name)):
                    taken[j] = True
            k = text.find(name, k + 1)
    return sorted(found)


def check_choices(c: Contest) -> list[Failure]:
    """A choice question's `[choices]` (docs/SCRIPT-FORMAT.md, STANDARD.md
    section 8): at least two options, each printed and drawn alike, its
    letter and label verbatim in the cited source, its letters in ballot
    order; no yes/no lines on the card; and the narration naming every
    option the same number of times, each once in the `choices` section,
    in ballot order, on the grid page that shows it."""
    ch = c.script.choices
    if ch is None:
        return []
    out = []

    def fail(msg, section=None, line=None):
        out.append(Failure("choices", msg, section, line))

    card = c.script.card
    if card is not None and (card.yes is not None or card.no is not None):
        fail("the card has 'yes'/'no' lines, but a choice question has no "
             "yes or no: the card lists the choices instead")
    opts = ch.choices
    if len(opts) < 2:
        fail(f"has {len(opts)} choice{'' if len(opts) == 1 else 's'}; a "
             f"choice question needs at least 2")
    ok_labels = True
    for i, o in enumerate(opts):
        what = f"choice[{i}]"
        if not isinstance(o.label, str) or not o.label.strip():
            fail(f"{what} has no 'label' (a non-empty string)")
            ok_labels = False
            continue
        what = f"choice {o.label!r}"
        if o.letter is not None and (not isinstance(o.letter, str)
                                     or not o.letter.strip()):
            fail(f"{what}: 'letter' must be a non-empty string")
        if o.spoken is not None:
            if not isinstance(o.spoken, str) or not o.spoken.strip():
                fail(f"{what}: 'spoken' must be a non-empty string")
                ok_labels = False
            elif _normalise(o.spoken) not in spoken_forms(o.label):
                fail(f"{what}: spoken {o.spoken!r} is not the label as "
                     f"printed, with or without its parenthesised parts")
                ok_labels = False
        for msg in _library_problems(o.illustration, "illustration"):
            fail(f"{what} {msg}")
    lettered = [o.letter is not None for o in opts]
    if any(lettered) and not all(lettered):
        fail("some choices have a 'letter' and some do not: every choice "
             "has one, or none does")
    elif all(lettered) and opts and all(isinstance(o.letter, str)
                                        for o in opts):
        if not _letter_series([o.letter for o in opts]):
            fail(f"letters {', '.join(o.letter for o in opts)} are not in "
                 f"ballot order (a, b, c ...; A, B, C ...; or 1, 2, 3 ...)")
    labels = [o.label for o in opts if isinstance(o.label, str)]
    if len(set(labels)) != len(labels):
        fail("two choices have the same label")

    # the source, and each option verbatim in it
    src = None
    if not isinstance(ch.source, str) or not ch.source:
        fail("[choices] has no 'source' (the source id its options are "
             "quoted from)")
    else:
        src = c.source(ch.source)
        if src is None:
            fail(f"source {ch.source!r} is not in sources.toml")
        elif card is not None and isinstance(card.source, str) \
                and card.source != ch.source:
            fail(f"source {ch.source!r} is not the card's {card.source!r}: "
                 f"the card lists the choices, verbatim from its own source")
    if src is not None:
        path = (c.path / src.file).resolve()
        if path.is_relative_to(c.path.resolve()) and path.is_file():
            try:
                archived = _archived_text(path)
            except UnreadableSource as e:
                fail(f"cannot read source {ch.source!r} ({src.file}) to "
                     f"check the choices' labels: {e}")
            else:
                for o in opts:
                    if isinstance(o.label, str) and o.label.strip() \
                            and not _in_text(o.printed, archived):
                        fail(f"choice {o.printed!r} does not appear verbatim "
                             f"in source {ch.source!r} ({src.file})")

    if ok_labels and len(opts) >= 2:
        out += _choice_narration(c, opts)
    return out


def _choice_narration(c: Contest, opts: tuple[Choice, ...]) -> list[Failure]:
    """The narration's side of check_choices: each option named once in
    the `choices` section, in ballot order, while its grid page is up;
    as often as every other over the whole script; and one `choices`
    visual per grid page, the first on the section's first line, and no
    other visual in the section or `choices` visual outside it."""
    out = []

    def fail(msg, section=None, line=None):
        out.append(Failure("choices", msg, section, line))

    names = [_normalise(o.said) for o in opts]
    counts = Counter()
    for label, sec in c.script.labelled():
        for i, line in enumerate(sec.lines):
            for _, k in _occurrences(_normalise(line.text), names):
                counts[k] += 1
            v = line.visual
            if sec.id != CHOICES and v is not None and v.kind == "choices":
                fail(f"a 'choices' visual belongs only in the {CHOICES!r} "
                     f"section", label, i)
    if len(set(counts[k] for k in range(len(opts)))) > 1:
        said = ", ".join(f"{opts[k].said!r} {counts[k]}"
                         for k in range(len(opts)))
        fail(f"the narration names the choices unequally often ({said}); "
             f"every choice is named as often as every other")

    secs = [(label, sec) for label, sec in c.script.labelled()
            if sec.id == CHOICES]
    if len(secs) != 1:
        return out  # check_template reports it
    label, sec = secs[0]
    want = grid.pages(len(opts))
    at = []
    for i, line in enumerate(sec.lines):
        v = line.visual
        if v is None:
            continue
        if v.kind != "choices":
            fail(f"the {CHOICES!r} section shows only the choices' grid; "
                 f"this line has a {v.kind!r} visual", label, i)
        else:
            at.append(i)
    if len(at) != len(want):
        fail(f"has {len(at)} 'choices' visual{'' if len(at) == 1 else 's'}; "
             f"{len(opts)} choices take {len(want)} grid page"
             f"{'' if len(want) == 1 else 's'} "
             f"({' + '.join(str(len(p)) for p in want)}), one visual each",
             label)
        return out
    if at[0] != 0:
        fail("the first grid page must come with the section's first line",
             label, at[0])
    # each page's options, in ballot order, in the lines it is up for
    order = []
    for p, (a, page) in enumerate(zip(at, want)):
        b = at[p + 1] if p + 1 < len(at) else len(sec.lines)
        text = " ".join(_normalise(ln.text) for ln in sec.lines[a:b])
        found = _occurrences(text, names)
        for k in page:
            n = sum(1 for _, j in found if j == k)
            if n != 1:
                fail(f"choice {opts[k].said!r} is named {n} times while its "
                     f"grid page is up; name it exactly once", label, a)
        order += [j for _, j in found if j in page]
        stray = sorted({j for _, j in found if j not in page})
        for j in stray:
            fail(f"choice {opts[j].said!r} is named while grid page "
                 f"{p + 1} is up, which does not show it", label, a)
    if order != sorted(order) and len(set(order)) == len(order):
        fail("the narration lists the choices out of ballot order: "
             + ", ".join(repr(opts[k].said) for k in order), label)
    return out


def check_judgment_words(c: Contest, words: tuple[str, ...]) -> list[Failure]:
    """STANDARD.md 3.1: no judgment word in a heading, a line or anything
    a visual shows. The `[card]` is exempt: it quotes the official page
    verbatim, and is not the narrator's voice."""
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


def needs_narration(c: Contest) -> bool:
    """Whether `c`'s script is still to be narrated: its narration is
    missing, or stale for the current script. The checks that stand in for
    what only narrating would otherwise reveal (check_speakability,
    check_spoken_parity, check_side_basis's requirement) apply only then:
    a current narration already passed the real transcript and airtime
    checks."""
    return narration.narration_state(c) != narration.CURRENT


def check_speakability(c: Contest, risks: tuple[Risk, ...],
                       pieces: tuple[narration.NarrationLine, ...] | None = None
                       ) -> list[Failure]:
    """No narrated line uses a spelling the narration's transcript check
    mishears (standard/speakability.txt). Only the narration: the card and
    on-screen items are not spoken. `pieces` is the text to lint, each
    piece tagged with its line (default: every line); check_contest passes
    only the phrases `say` would synthesise afresh
    (narration.unreused_phrases), since a reused phrase already passed the
    real transcript check."""
    if pieces is None:
        pieces = tuple(narration.NarrationLine(label, i, line.text)
                       for label, sec in c.script.labelled()
                       for i, line in enumerate(sec.lines))
    out = []
    for piece in pieces:
        taken: list[tuple[int, int]] = []  # one report per token
        for risk in risks:
            for m in risk.pattern.finditer(piece.text):
                if any(m.start() < e and s < m.end() for s, e in taken):
                    continue
                taken.append(m.span())
                out.append(Failure(
                    "speakability",
                    f"{m.group(0)!r} in {piece.text!r}: {risk.reason}; "
                    f"instead, {risk.suggestion}", piece.section, piece.index))
    return out


def _shown_text(v: Visual) -> list[tuple[str, str]]:
    """The words a visual puts on screen, as (key, text) pairs."""
    out = []
    for key in ("title", "labels", "items", "stamp"):
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
    fresh = needs_narration(c)
    unreused = narration.unreused_phrases(c) if fresh else None
    return [
        *check_contest_id(c),
        *check_voters(c),
        *check_line_citations(c),
        *check_cited_sources_exist(c),
        *check_background_only(c),
        *check_university_guide(c),
        *check_questions(c),
        *check_visuals(c),
        *check_chart_precision(c),
        *check_ballot(c),
        *check_card(c),
        *check_highlight_balance(c),
        *check_choices(c),
        *check_sources(c),
        *check_template(c),
        *check_side_headings(c),
        *check_side_parity(c),
        *check_side_visuals(c),
        *check_side_list_items(c),
        *check_airtime(c),
        *(check_spoken_parity(c, unreused) if fresh else ()),
        *check_side_basis(c, required=fresh),
        *check_judgment_words(c, standard.judgment_words),
        *check_naming(c, standard.proper_words),
        *(check_speakability(c, standard.speakability, unreused)
          if fresh else ()),
        *check_standard_version(c, standard.version),
    ]
