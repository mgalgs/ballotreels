"""The standard's machine checks on a contest's script and sources.

check_contest() runs every check and returns every failure; an empty
list means the contest passes. Checks that need data another check found
broken (say, side parity without exactly one yes and one no section)
skip that part rather than report the same defect twice.
"""

from __future__ import annotations

import html
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import narration, storyboard
from .contest import CARD_KEYS, Card, Contest, Line, Section, Visual
from .illustrations import load_library
from .standard import (BACKGROUND, BACKGROUND_ONLY_KINDS, SOURCE_KINDS,
                       TEMPLATES, Standard, Template, judgment_word_pattern,
                       load_standard)

SIDE_TOLERANCE = 0.05
CHART_KINDS = ("bars", "share", "series", "figure")
VISUAL_KINDS = (*CHART_KINDS, "timeline", "list", "illustration", "page")
# The kind of source a [card] quotes: the measure's official page.
CARD_SOURCE_KIND = "official-title-summary"
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


def _illustration_problems(v: Visual) -> list[str]:
    """An `illustration`: a name in the library, whose file exists."""
    out = []
    _forbid(v, ("title", "source", "unit", "labels", "values", "figure",
                "items", "focus", "highlight"), out)
    if v.name is None:
        out.append("has no 'name'")
    elif not isinstance(v.name, str) or not v.name:
        out.append("'name' must be a non-empty string")
    else:
        entry = load_library().get(v.name)
        if entry is None:
            out.append(f"names {v.name!r}, which is not in "
                       f"film/illustrations/illustrations.toml")
        elif not entry.path.is_file():
            out.append(f"names {v.name!r}, whose file {entry.file!r} "
                       f"does not exist")
    return out


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
            for msg in _visual_problems(c, line, line.visual):
                out.append(Failure("visual", f"{what} {msg}", label, i))
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


@lru_cache(maxsize=8)
def _archived_text(path: Path) -> str:
    return plain_text(path.read_text(encoding="utf-8", errors="replace"))


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


def check_card(c: Contest) -> list[Failure]:
    """The `[card]`, if any: every key present, a source of the official
    page's kind, and each quoted field verbatim in that source's archived
    text (docs/SCRIPT-FORMAT.md)."""
    card = c.script.card
    if card is None:
        return []
    out = []

    def fail(msg):
        out.append(Failure("card", msg))

    for key in CARD_KEYS:
        value = getattr(card, key)
        if value is None:
            fail(f"has no {key!r}")
        elif not isinstance(value, str) or not value.strip():
            fail(f"{key!r} must be a non-empty string")
    if not isinstance(card.source, str) or not card.source:
        return out
    src = c.source(card.source)
    if src is None:
        fail(f"source {card.source!r} is not in sources.toml")
        return out
    if src.kind != CARD_SOURCE_KIND:
        fail(f"source {card.source!r} is of kind {src.kind!r}; a card "
             f"quotes a source of kind {CARD_SOURCE_KIND!r}")
        return out
    path = (c.path / src.file).resolve()
    if not path.is_relative_to(c.path.resolve()) or not path.is_file():
        return out  # check_sources reports it
    archived = _archived_text(path)
    for key, value in card.quoted():
        if isinstance(value, str) and value.strip() \
                and _normalise(value) not in archived:
            fail(f"{key!r} does not appear verbatim in source "
                 f"{card.source!r} ({src.file})")
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
    already requires both sides to have a 'list' or neither)."""
    by_side: dict[str, list[Section]] = {}
    for sec in c.script.sections:
        if sec.side is not None:
            by_side.setdefault(sec.side, []).append(sec)
    yes, no = by_side.get("yes", []), by_side.get("no", [])
    if len(yes) != 1 or len(no) != 1:
        return []  # a template failure; nothing to compare

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
    if gap > narration.SIDE_PAD_CAP:
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


def _shown_text(v: Visual) -> list[tuple[str, str]]:
    """The words a visual puts on screen, as (key, text) pairs."""
    out = []
    for key in ("title", "labels", "items"):
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
        *check_card(c),
        *check_highlight_balance(c),
        *check_sources(c),
        *check_template(c),
        *check_side_parity(c),
        *check_side_visuals(c),
        *check_side_list_items(c),
        *check_airtime(c),
        *check_judgment_words(c, standard.judgment_words),
        *check_standard_version(c, standard.version),
    ]
