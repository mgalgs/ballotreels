"""How each state's ballot and official voter guide word a measure.

The measure template is the same everywhere (STANDARD.md 2.1); what
differs by state is the wording the film and the card quote from the
state's own documents: the badge over the measure's number, the name of
the guide the card is a page of, the heading of its fiscal statement and
the ballot's words for the two choices (docs/SCRIPT-FORMAT.md). Each
state's entry gives its own; a measure in a state with no entry fails
the checks rather than borrowing another state's words.

This lives in code, not in data/<election>/contests.toml, because a
worker renders a copy of the contest directory alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ballot:
    guide: str               # the official publication the card is a page of
    fiscal_label: str        # the heading of its fiscal statement, as printed
    choices: tuple[str, str]  # the ballot's words for the yes and no sides
    card_source_kind: str    # the source kind a `[card]` quotes
    # designation words the guide abbreviates on its badge, as printed
    badges: dict[str, str] = field(default_factory=dict)


BALLOTS: dict[str, Ballot] = {
    "ca": Ballot(guide="Official Voter Information Guide",
                 fiscal_label="Fiscal Impact:",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary",
                 badges={"Proposition": "PROP"}),
    "ut": Ballot(guide="Voter Information Pamphlet",
                 fiscal_label="Fiscal Effects",
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary"),
}

_STATE = re.compile(r"/state:([a-z]{2})(?:/|$)")


def state_of(division: str) -> str | None:
    """The two-letter state in an OCD division id, or None."""
    m = _STATE.search(division)
    return m.group(1) if m else None


def ballot_for(division: str) -> Ballot | None:
    """The wording for the state `division` is in, or None if it has none."""
    return BALLOTS.get(state_of(division) or "")


def designation(title: str, number: str) -> str | None:
    """The word `title` uses for its measures, from the word just before
    `number` in its lead (before any colon): "Proposition" in
    "Proposition 2: ...", "Amendment" in "Constitutional Amendment A:
    ...". None when the lead has no word before the number."""
    lead = title.split(":", 1)[0]
    m = re.search(rf"([A-Za-z]+)\s+{re.escape(number)}\s*$", lead)
    return m.group(1) if m else None


def badge(ballot: Ballot, title: str, number: str) -> str | None:
    """The badge word over the measure's number on its card: its
    designation, upper-case, or the guide's abbreviation of it."""
    word = designation(title, number)
    if word is None:
        return None
    return ballot.badges.get(word, word.upper())
