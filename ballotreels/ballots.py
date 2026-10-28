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
    # True where the card's source is set in columns that pdftotext reads
    # out of order (Louisiana's one-sheet statements), so a card quote may
    # run across one column break and lose a hyphen at a line's end
    # (checks._card_quote_in)
    card_column_breaks: bool = False


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

    # Georgia's Secretary of State prints the full text of each
    # amendment the General Assembly proposes, its ballot question and a
    # summary in its booklet "Proposed Constitutional Amendments"; the
    # ballot prints the choices "( ) YES" and "( ) NO". The booklet
    # prints no fiscal statement. Its amendments are numbered "1" to
    # "3" (the badge: AMENDMENT, from the title's designation).
    "ga": Ballot(guide="Proposed Constitutional Amendments",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Hawaii's Office of Elections prints each proposed constitutional
    # amendment in its "2026 Voter Guide" on one page of statements
    # "PROVIDED BY THE STATE OF HAWAII, DEPARTMENT OF THE ATTORNEY
    # GENERAL": its title ("QUESTION #1: ..."; the badge says QUESTION,
    # from the contest title's "Question 1"), the ballot question, an
    # explanation and the meaning of a "yes" and a "no" vote. No fiscal
    # statement exists for an amendment the Legislature proposes.
    "hi": Ballot(guide="2026 Voter Guide",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Colorado's Legislative Council Staff prints each measure's Quick
    # Reference entry, analysis and ballot title in the 2026 Colorado
    # State Ballot Information Booklet (the Blue Book), and its full
    # statement on each headed "Fiscal Impact Statement". The ballot
    # prints the choices "Yes/For" and "No/Against" (SB 26-135, section
    # 9); the badge is the designation as printed: AMENDMENT 81,
    # PROPOSITION NN.
    "co": Ballot(guide="State Ballot Information Booklet",
                 fiscal_label="Fiscal Impact Statement",
                 choices=("Yes/For", "No/Against"),
                 card_source_kind="official-title-summary"),

    # Rhode Island's Secretary of State prints each bond question's
    # ballot label, its "Your vote to “Approve” means" and "Your vote to
    # “Reject” means" lines, its explanation and its cost in the "Voter
    # Information Handbook" ("Rhode Island Voter Information Handbook
    # 2026" in its page footers). Each question is "Question 1" (badge
    # QUESTION, from the title's designation), its cost table is headed
    # "Total cost:", and the ballot prints the choices "Approve" and
    # "Reject".
    "ri": Ballot(guide="Voter Information Handbook",
                 fiscal_label="Total cost:",
                 choices=("Approve", "Reject"),
                 card_source_kind="official-title-summary"),

    # Arkansas publishes no official voter guide. The Secretary of State
    # prints each referred measure in a "NOTICE TO THE PUBLIC" (its popular
    # name, ballot title and text, or for a bond act its ballot title and
    # ballot question), headed "ISSUE NO. 1" (badge ISSUE, from the title's
    # designation; the "No." is skipped). Each elector "shall vote for or
    # against", and the ballot prints "FOR" and "AGAINST". No fiscal
    # statement exists for any of them.
    "ar": Ballot(guide="Notice to the Public",
                 fiscal_label=None,
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary"),

    # New Mexico's Secretary of State prints each constitutional
    # amendment's ballot title, purpose and the Legislative Council
    # Service's arguments, and each general obligation bond question, in
    # its "2026 General Election Voter Guide" (the year left out here, as
    # Nevada's is). Each is headed "Constitutional Amendment 1" or "Bond
    # Question 1" (badge BOND QUESTION, as printed, rather than the bare
    # QUESTION), and the ballot prints the choices "For:" and "Against:".
    # The guide prints no fiscal statement for any of them.
    "nm": Ballot(guide="General Election Voter Guide",
                 fiscal_label=None,
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary",
                 badges={"Question": "BOND QUESTION"}),

    # Virginia's Department of Elections publishes, for each proposed
    # constitutional amendment, a special explanation (Code § 30-19.9)
    # headed "EXPLANATION FOR VOTERS" over its "QUESTION 1" (the badge:
    # QUESTION), with the ballot question and full text; its brochure
    # carries the same wording. The card quotes the explanation. The
    # fiscal statement is the Department of Planning and Budget's,
    # headed "State Fiscal Impact Statement"; no card quotes it. The
    # ballot's choices are "Yes" and "No".
    "va": Ballot(guide="Explanation for Voters",
                 fiscal_label="State Fiscal Impact Statement",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Maryland mails no voter pamphlet. The State Board of Elections posts
    # "Ballot Questions for the November 3, 2026 Election" (Election Law
    # 7-103(e)): each question headed "Question 1", its title, ballot
    # text and "A vote FOR / AGAINST" lines, and the choices "For the
    # Constitutional Amendment" and "Against the Constitutional
    # Amendment". It prints no fiscal statement; the Department of
    # Legislative Services' Fiscal and Policy Note heads its own "Fiscal
    # Summary". No card quotes it, so the heading is never drawn.
    "md": Ballot(guide="Ballot Questions for the November 3, 2026 Election",
                 fiscal_label="Fiscal Summary",
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary"),

    # Louisiana has no voter pamphlet. Its Secretary of State's
    # "Statements of Proposed Constitutional Amendments" (R.S. 18:431 and
    # 18:552) prints each amendment's ballot question, Act, "Abstract"
    # and "Present Constitution / Proposed Constitutional Amendment"
    # paragraphs, numbered 1 to 10 in ballot order, and no fiscal
    # statement; each Act submits its proposition for electors "to vote
    # YES or NO". The badge takes "Amendment" from the contest title.
    # The sheet is one page of four columns: No. 6's ballot question runs
    # from the foot of one column to the head of the next, and No. 1's
    # breaks "one-time" at a line's end, which pdftotext joins.
    "la": Ballot(guide="Statements of Proposed Constitutional Amendments",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary",
                 card_column_breaks=True),

    # Alabama publishes no voter pamphlet. Its Fair Ballot Commission
    # approves a "BALLOT STATEMENT" for each statewide amendment (Ala.
    # Code 17-6-81): the ballot text, sponsor, placement ("Statewide
    # Amendment 1", badge AMENDMENT) and a plain-language summary, whose
    # cost sentence ("There are no costs or taxes associated with
    # Amendment 1.") sits under no heading of its own, so there is no
    # fiscal label. The ballot prints the choices "Yes ( ) No ( )".
    "al": Ballot(guide="Fair Ballot Commission Ballot Statement",
                 fiscal_label=None,
                 choices=("Yes", "No"),
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
