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

from .checks import Failure, UnreadableSource, _loose, _loose_archived
from .contest import ContestError, load_contest
from .index import ContestIndexError, load_index

GLANCE_FILE = "glance.toml"

# The kinds a figure may be quoted from: the official fiscal statement,
# or the official guide's fiscal section (STANDARD.md rule 1.2).
GLANCE_KINDS = frozenset({"official-fiscal-analysis",
                          "official-title-summary"})
DIRECTIONS = frozenset({"cost", "revenue-loss", "revenue-gain", "savings",
                        "mixed"})
# Why an entry has no amount: the statement prints no dollar figure, says
# the effect cannot be determined, or says there is no material effect.
STATUSES = frozenset({"none-printed", "not-determined",
                      "no-material-impact"})
PERIODS = frozenset({"per-year", "one-time", "unstated"})
_PERIOD_SPAN = re.compile(r"^(over|every) ([2-9]|[1-9]\d+) years$")
KEYS = frozenset({"source", "quote", "amount", "period", "direction",
                  "status"})

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
    period: str | None = None     # with `amount` only
    direction: str | None = None  # only as the quote states it
    status: str | None = None     # None when `amount` is set


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
        if period is not None:
            raise GlanceError(f"{where}: 'period' goes with an 'amount' "
                              f"only")
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
                       amount=amount, period=period, direction=direction,
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
    source's archived text (compared as a side's basis is); and its
    amount is the largest dollar figure the quote prints."""
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
        except UnreadableSource as e:
            fail(f"cannot read source {entry.source!r} ({src.file}): {e}")
            continue
        if _loose(entry.quote) not in text:
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
        elif entry.status == "none-printed" \
                and (figures := dollar_figures(entry.quote)):
            fail(f"status is 'none-printed', but the quote prints "
                 f"{figures}: give the largest as 'amount'")
    return out
