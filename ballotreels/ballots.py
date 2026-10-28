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
    # the heading of its fiscal statement, as printed; None where the
    # guide prints none (Arizona's legislative referrals have no fiscal
    # summary), so a card there has no `fiscal` quote
    fiscal_label: str | None
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
    "wa": Ballot(guide="Voters' Pamphlet",
                 fiscal_label="Fiscal Impact Statement",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # The District of Columbia, under the state:dc id the site uses
    # (ballotreels/site/config.py). The Board of Elections' Voter Guide
    # prints "INITIATIVE MEASURE NO. 86" (the badge says INITIATIVE, as
    # its Spanish page's "INICIATIVA NO. 86" shortens it) and the choices
    # "Yes, to approve" and "No, to reject"; the Chief Financial
    # Officer's statement is headed "Fiscal Impact Statement".
    "dc": Ballot(guide="Voter Guide",
                 fiscal_label="Fiscal Impact Statement",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary",
                 badges={"Measure": "INITIATIVE"}),
    # Florida's Division of Elections booklet, "Proposed Constitutional
    # Amendments for the General Election", prints each amendment's
    # ballot title and summary and no fiscal statement; the Legislature's
    # bill analyses carry one, headed "Fiscal Impact Statement" (the
    # Senate's) or "FISCAL OR ECONOMIC IMPACT" (the House's). No card
    # quotes it, so the one heading here is never drawn.
    "fl": Ballot(guide="Proposed Constitutional Amendments",
                 fiscal_label="Fiscal Impact Statement",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    "id": Ballot(guide="Idaho Voter Pamphlet",
                 fiscal_label="FISCAL IMPACT STATEMENT",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    "az": Ballot(guide="Arizona's General Election Guide",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # Ohio's Secretary of State prints each statewide issue's ballot
    # language, explanation, arguments and text in one report, headed on
    # every page "Proposed Amendment to the Ohio Constitution"; its
    # ballot language heads the issue "ISSUE 3" and prints the choices
    # "YES" and "NO". No fiscal statement exists: Ohio requires none for
    # an amendment the General Assembly proposes.
    "oh": Ballot(guide="Proposed Amendment to the Ohio Constitution",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # Montana's Secretary of State prints each ballot issue's ballot
    # language, complete text and arguments in its Voter Information
    # Pamphlet. The ballot prints the choices "YES on Constitutional
    # Amendment CI-132" and "YES on Initiative I-194" (the badge takes
    # the designation word from them: AMENDMENT CI-132, INITIATIVE
    # I-194). No fiscal statement is printed: Montana prints one only
    # where the fiscal note finds an impact.
    "mt": Ballot(guide="Voter Information Pamphlet",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # Nevada's Secretary of State prints each statewide question's
    # ballot question, explanation and digest, arguments, Legislative
    # Counsel Bureau fiscal note and full text in its booklet "2026
    # Statewide Ballot Questions" (the year left out here, as Utah's
    # "2026 Utah Voter Information Pamphlet" leaves it). Each question
    # is headed "QUESTION 6" (badge QUESTION, from the title's
    # designation), its fiscal statement "Fiscal Note", and the ballot
    # prints the choices "Yes" and "No".
    "nv": Ballot(guide="Statewide Ballot Questions",
                 fiscal_label="Fiscal Note",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # Massachusetts's Secretary of the Commonwealth prints each ballot
    # question's wording, the Attorney General's summary, "WHAT YOUR VOTE
    # WILL DO" (its "A YES VOTE" and "A NO VOTE" lines), the Executive
    # Office of Administration and Finance's "STATEMENT OF FISCAL
    # CONSEQUENCES" and the arguments in its Information for Voters. The
    # booklet heads each "QUESTION 1" (the badge: QUESTION 1).
    "ma": Ballot(guide="Information for Voters",
                 fiscal_label="STATEMENT OF FISCAL CONSEQUENCES",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # North Dakota's Secretary of State mails every voter "North Dakota
    # Statewide Ballot Measure Information" (NDCC 16.1-01-18): each
    # measure's explanation, its YES and NO meanings, a box headed
    # "FISCAL IMPACT" and the ballot as it will appear, with the choices
    # "YES" and "NO". Its measures are "Constitutional Measure No. 1" and
    # "Initiated Constitutional Measure No. 2"; designation() skips the
    # "No.", so the badge reads MEASURE.
    "nd": Ballot(guide="North Dakota Statewide Ballot Measure Information",
                 fiscal_label="FISCAL IMPACT",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),
    # Wyoming's Secretary of State prints the one proposition's ballot
    # language, its "Estimated Fiscal Impact:" and its full text in "2026
    # General Election Statewide Ballot Propositions", and the ballot's
    # choices "FOR" and "AGAINST". The proposition is headed "PROPOSED
    # INITIATIVE PROPOSITION NUMBER ONE": its number is the word "One",
    # so the word before it is "Number", and the badge says PROPOSITION.
    "wy": Ballot(guide="2026 General Election Statewide Ballot Propositions",
                 fiscal_label="Estimated Fiscal Impact:",
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary",
                 badges={"Number": "PROPOSITION"}),
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
    ...", "Measure" in "Initiative Measure No. 86: ..." (a "No." before
    the number is skipped). None when the lead has no word before the
    number."""
    lead = title.split(":", 1)[0]
    m = re.search(rf"([A-Za-z]+)\s+(?:No\.\s*)?{re.escape(number)}\s*$",
                  lead)
    return m.group(1) if m else None


def badge(ballot: Ballot, title: str, number: str) -> str | None:
    """The badge word over the measure's number on its card: its
    designation, upper-case, or the guide's abbreviation of it."""
    word = designation(title, number)
    if word is None:
        return None
    return ballot.badges.get(word, word.upper())
