"""The "ballot at a glance" figures: data/<election>/glance.toml.

One entry per measure on the election's ballot, keyed by the measure's
directory name (its slug), giving the size of the official fiscal
estimate as the official statement itself prints it: the quote, the
source it is quoted from, and a machine sort value (docs/SCRIPT-FORMAT.md,
"glance.toml"). The loader checks shape; check_glance() checks the
entries against the contest index and the archived sources.
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .checks import (Failure, UnreadableSource, _loose, _loose_archived,
                     _loose_unshifted)
from .contest import ContestError, load_contest
from .index import ContestIndexError, load_index

GLANCE_FILE = "glance.toml"

# The kinds a figure may be quoted from: the official fiscal statement,
# or the official guide's fiscal section (STANDARD.md rule 1.2).
GLANCE_KINDS = frozenset({"official-fiscal-analysis",
                          "official-title-summary"})
DIRECTIONS = frozenset({"cost", "revenue-loss", "revenue-gain", "savings",
                        "mixed"})
# Why an entry has no amount: the statement prints no dollar figure, sizes
# the effect only in words ("tens of millions of dollars"), says the
# effect cannot be determined, or says there is no material effect.
STATUSES = frozenset({"none-printed", "words", "not-determined",
                      "no-material-impact"})
PERIODS = frozenset({"per-year", "one-time", "unstated"})
_PERIOD_SPAN = re.compile(r"^(over|every) ([2-9]|[1-9]\d+) years$")
KEYS = frozenset({"source", "quote", "amount", "magnitude", "period",
                  "direction", "status"})

# The sizes a statement may give in words, as the lower bound each names,
# in dollars. "a few <unit>" names its unit's bound: "a few hundred
# thousand" is 100000. Nothing else counts.
MAGNITUDES = {"thousands": 10**3, "tens of thousands": 10**4,
              "hundreds of thousands": 10**5, "millions": 10**6,
              "tens of millions": 10**7, "hundreds of millions": 10**8,
              "billions": 10**9, "tens of billions": 10**10}
_A_FEW = {"thousands": "thousand", "hundreds of thousands": "hundred thousand",
          "millions": "million", "hundreds of millions": "hundred million",
          "billions": "billion"}
_WORDS = [(re.compile(r"\b(?:" + "|".join(
              r"\s+".join(map(re.escape, alt.split()))
              for alt in (phrase, "a few " + _A_FEW.get(phrase, phrase)))
              + r")\b", re.IGNORECASE), value)
          for phrase, value in MAGNITUDES.items()]

_SCALES = {None: 1, "thousand": 10**3, "million": 10**6,
           "billion": 10**9, "trillion": 10**12}
_DOLLARS = re.compile(
    r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:\s+(thousand|million|billion|trillion)\b)?", re.IGNORECASE)


class GlanceError(Exception):
    """A glance.toml that cannot be loaded, or an entry that breaks a
    rule of its format."""


@dataclass(frozen=True)
class GlanceEntry:
    slug: str
    source: str
    quote: str | None = None
    amount: int | None = None     # dollars; None when `status` is set
    magnitude: int | None = None  # with `amount`, or status "words"
    period: str | None = None     # with `amount`, or status "words"
    direction: str | None = None  # only as the quote states it
    status: str | None = None     # None when `amount` is set

    @property
    def sort_value(self) -> int | None:
        """The size the list sorts by: the larger of `amount` and
        `magnitude`; None when the entry has neither."""
        sizes = [v for v in (self.amount, self.magnitude) if v is not None]
        return max(sizes, default=None)


def valid_period(period: str) -> bool:
    return period in PERIODS or _PERIOD_SPAN.match(period) is not None


def dollar_figures(quote: str) -> list[int]:
    """Every dollar amount printed in `quote`, in dollars, in order:
    "$2.7 billion" is 2700000000, "$314,000" is 314000. Only figures
    printed with a dollar sign count; "tens of millions of dollars" is
    not a figure."""
    s = unicodedata.normalize("NFKC", quote)
    out = []
    for m in _DOLLARS.finditer(s):
        whole, frac, scale = m.groups()
        value = (Decimal(whole.replace(",", "") + (frac or ""))
                 * _SCALES[scale.lower() if scale else None])
        if value == value.to_integral_value():
            out.append(int(value))
    return out


def word_magnitudes(quote: str) -> list[int]:
    """The MAGNITUDES whose phrase `quote` prints, smallest first: "tens
    of millions of dollars" is 10000000 (and 1000000, for "millions")."""
    s = unicodedata.normalize("NFKC", quote)
    return [value for pattern, value in _WORDS if pattern.search(s)]


def _entry(slug: str, raw: object, where: str) -> GlanceEntry:
    if not isinstance(raw, dict):
        raise GlanceError(f"{where}: must be a table")
    unknown = sorted(set(raw) - KEYS)
    if unknown:
        raise GlanceError(f"{where}: unknown key {unknown[0]!r}")
    for key in ("source", "quote", "period", "direction", "status"):
        if key in raw and not (isinstance(raw[key], str) and raw[key]):
            raise GlanceError(f"{where}: {key!r} must be a non-empty string")
    if "source" not in raw:
        raise GlanceError(f"{where}: needs 'source'")
    amount = raw.get("amount")
    if amount is not None and (isinstance(amount, bool)
                               or not isinstance(amount, int)
                               or amount <= 0):
        raise GlanceError(f"{where}: 'amount' must be a whole number of "
                          f"dollars, above zero")
    magnitude = raw.get("magnitude")
    if magnitude is not None and (isinstance(magnitude, bool)
                                  or magnitude not in MAGNITUDES.values()):
        raise GlanceError(f"{where}: 'magnitude' must be one of "
                          f"{sorted(MAGNITUDES.values())}")
    status, period = raw.get("status"), raw.get("period")
    direction, quote = raw.get("direction"), raw.get("quote")
    if (amount is None) == (status is None):
        raise GlanceError(f"{where}: needs exactly one of 'amount' and "
                          f"'status'")
    if amount is not None:
        if quote is None:
            raise GlanceError(f"{where}: an 'amount' needs the 'quote' "
                              f"that states it")
        if period is None:
            raise GlanceError(f"{where}: an 'amount' needs its 'period'")
        if not valid_period(period):
            raise GlanceError(
                f"{where}: 'period' must be one of {sorted(PERIODS)}, "
                f"'over N years' or 'every N years', got {period!r}")
    else:
        if status not in STATUSES:
            raise GlanceError(f"{where}: 'status' must be one of "
                              f"{sorted(STATUSES)}, got {status!r}")
        if status == "words":
            if magnitude is None:
                raise GlanceError(f"{where}: status 'words' needs its "
                                  f"'magnitude'")
            if period is None:
                raise GlanceError(f"{where}: status 'words' needs its "
                                  f"'period'")
            if not valid_period(period):
                raise GlanceError(
                    f"{where}: 'period' must be one of {sorted(PERIODS)}, "
                    f"'over N years' or 'every N years', got {period!r}")
        elif period is not None:
            raise GlanceError(f"{where}: 'period' goes with an 'amount' "
                              f"or status 'words' only")
        if magnitude is not None and status != "words":
            raise GlanceError(f"{where}: 'magnitude' goes with an 'amount' "
                              f"or status 'words' only")
        if quote is None and status != "none-printed":
            raise GlanceError(f"{where}: status {status!r} needs the "
                              f"'quote' that says so")
    if direction is not None and direction not in DIRECTIONS:
        raise GlanceError(f"{where}: 'direction' must be one of "
                          f"{sorted(DIRECTIONS)}, got {direction!r}")
    if direction is not None and quote is None:
        raise GlanceError(f"{where}: a 'direction' needs the 'quote' that "
                          f"states it")
    return GlanceEntry(slug=slug, source=raw["source"], quote=quote,
                       amount=amount, magnitude=magnitude,
                       period=period, direction=direction,
                       status=status)


def load_glance(election_dir: str | Path) -> dict[str, GlanceEntry] | None:
    """The entries of `<election_dir>/glance.toml`, by slug, in file
    order; None when the election has no such file."""
    path = Path(election_dir) / GLANCE_FILE
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return None
    except tomllib.TOMLDecodeError as e:
        raise GlanceError(f"{path}: {e}") from None
    return {slug: _entry(slug, raw, f"{path}: {slug!r}")
            for slug, raw in data.items()}


def check_glance(election_dir: str | Path) -> list[Failure] | None:
    """Check `<election_dir>/glance.toml`; None when there is none. Every
    measure in the election's contests.toml has an entry and every entry
    is such a measure; each entry's source is one of its contest's
    sources, of a kind in GLANCE_KINDS; its quote appears verbatim in that
    source's archived text (compared as a side's basis is); its amount is
    the largest dollar figure the quote prints, and its magnitude the
    largest size it names in words (MAGNITUDES), given wherever the quote
    of an amount or a "words" entry names one."""
    election_dir = Path(election_dir)
    try:
        entries = load_glance(election_dir)
    except GlanceError as e:
        return [Failure("glance", str(e))]
    if entries is None:
        return None
    try:
        index = load_index(election_dir)
    except ContestIndexError as e:
        return [Failure("glance", f"cannot load the contest index: {e}")]
    prefix = f"{index.election.id}-"
    measures = [e.id[len(prefix):] for e in index.entries
                if e.kind == "measure"]
    out = [Failure("glance", "measure has no entry", slug)
           for slug in measures if slug not in entries]
    for slug, entry in entries.items():
        def fail(msg):
            out.append(Failure("glance", msg, slug))

        if slug not in measures:
            fail("is not a measure in contests.toml")
            continue
        try:
            contest = load_contest(election_dir / slug)
        except ContestError as e:
            fail(f"cannot load the contest: {e}")
            continue
        src = contest.source(entry.source)
        if src is None:
            fail(f"source {entry.source!r} is not in its sources.toml")
            continue
        if src.kind not in GLANCE_KINDS:
            fail(f"source {entry.source!r} is {src.kind!r}, not a fiscal "
                 f"statement ({', '.join(sorted(GLANCE_KINDS))})")
            continue
        if entry.quote is None:
            continue
        path = (contest.path / src.file).resolve()
        if not path.is_relative_to(contest.path.resolve()) \
                or not path.is_file():
            fail(f"source {entry.source!r} has no archived file "
                 f"({src.file})")
            continue
        try:
            text = _loose_archived(path)
            # a PDF's shifted-font lines decoded (checks._unshift_line)
            unshifted = _loose_unshifted(path)
        except UnreadableSource as e:
            fail(f"cannot read source {entry.source!r} ({src.file}): {e}")
            continue
        quote = _loose(entry.quote)
        if quote not in text \
                and (unshifted is None or quote not in unshifted):
            fail(f"quote does not appear verbatim in source "
                 f"{entry.source!r} ({src.file})")
        if entry.amount is not None:
            figures = dollar_figures(entry.quote)
            if entry.amount not in figures:
                fail(f"amount {entry.amount} is not a dollar figure the "
                     f"quote prints ({figures or 'none'})")
            elif entry.amount != max(figures):
                fail(f"amount {entry.amount} is not the quote's largest "
                     f"dollar figure ({max(figures)})")
        elif entry.status in ("none-printed", "words") \
                and (figures := dollar_figures(entry.quote)):
            fail(f"status is {entry.status!r}, but the quote prints "
                 f"{figures}: give the largest as 'amount'")
        if entry.amount is not None or entry.status == "words":
            words = word_magnitudes(entry.quote)
            if entry.magnitude is None:
                if words:
                    fail(f"the quote names a size in words ({max(words)}): "
                         f"give it as 'magnitude'")
            elif entry.magnitude not in words:
                fail(f"magnitude {entry.magnitude} is not a size the quote "
                     f"names in words ({words or 'none'})")
            elif entry.magnitude != max(words):
                fail(f"magnitude {entry.magnitude} is not the largest size "
                     f"the quote names in words ({max(words)})")
    return out
