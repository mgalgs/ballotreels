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

    # the publication a measure's card is a page of where it is not the
    # guide (a measure the guide does not cover), by contest id
    guides: dict[str, str] = field(default_factory=dict)


BALLOTS: dict[str, Ballot] = {
    # A county measure's card is a page of its county's publication, not
    # the state's guide: San Diego's Voter Information Guide prints each
    # measure's ballot label and impartial analysis; Los Angeles prints
    # its ballot label only in the measure's proposed ordinance.
    "ca": Ballot(guide="Official Voter Information Guide",
                 fiscal_label="Fiscal Impact:",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary",
                 badges={"Proposition": "PROP"},
                 guides={
                     "ca-2026-11-03-sd-county-measure-a":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-sd-county-measure-b":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-la-county-measure-a":
                         "Proposed Ordinance of Measure A",
                     "ca-2026-11-03-la-county-measure-e":
                         "Proposed Ordinance of Measure E",
                     "ca-2026-11-03-san-diego-unified-measure-m":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-vista-unified-measure-n":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-la-mesa-spring-valley-measure-aa":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-santee-school-measure-bb":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-fallbrook-elementary-measure-k":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-grossmont-cuyamaca-measure-g":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-ramona-water-measure-p":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-jamul-dulzura-measure-h":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-mountain-empire-measure-l":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-julian-high-measure-j":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-pala-mesa-road-zone-measure-t":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-harris-annex-road-zone-measure-q":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-santee-measure-y":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-lemon-grove-measure-e":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-solana-beach-measure-c":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-oceanside-measure-s":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-oceanside-measure-r":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-coronado-measure-d":
                         "San Diego County Voter Information Guide",
                     "ca-2026-11-03-westminster-school-measure-b":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-laguna-beach-unified-measure-a":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-san-francisco-county-measure-g":
                         "San Francisco Voter Information Pamphlet & Sample Ballot",
                     "ca-2026-11-03-san-francisco-county-measure-h":
                         "San Francisco Voter Information Pamphlet & Sample Ballot",
                     "ca-2026-11-03-san-francisco-county-measure-i":
                         "San Francisco Voter Information Pamphlet & Sample Ballot",
                     "ca-2026-11-03-san-francisco-county-measure-j":
                         "San Francisco Voter Information Pamphlet & Sample Ballot",
                     "ca-2026-11-03-san-mateo-measure-h":
                         "City of San Mateo Resolution No. 84 (2026)",
                     "ca-2026-11-03-san-mateo-measure-f":
                         "City of San Mateo Resolution No. 85 (2026)",
                     "ca-2026-11-03-redwood-city-measure-e":
                         "Resolution No. 16425",
                     "ca-2026-11-03-san-bruno-measure-s":
                         "Resolution No. 2026-075",
                     "ca-2026-11-03-san-bruno-measure-dd":
                         "Resolution No. 2026-077",
                     "ca-2026-11-03-san-bruno-measure-ee":
                         "Resolution No. 2026-079",
                 }),
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

    # North Carolina prints no voter guide. Its one official explanation
    # is the Legislative Services Officer's "Official Summary
    # Explanation of 2026 Constitutional Amendments" (G.S. 147-54.10):
    # each amendment's ballot question, its choices "FOR" and "AGAINST"
    # (the State Board of Elections' list prints "For" and "Against"),
    # and an official summary, with no fiscal statement. The ballot heads
    # each only "Constitutional Amendment", with no number, so its cards
    # have no number and draw no badge.
    "nc": Ballot(guide="Official Summary Explanation",
                 fiscal_label=None,
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary"),

    # Nebraska's Secretary of State prints each initiative's ballot
    # language (its explanatory statements, "A vote “FOR” will ..." and
    # "A vote “AGAINST” means ...", and its question), full text and
    # arguments in the "Informational Pamphlet on Initiative Measures
    # Appearing on the 2026 General Election Ballot", which heads each
    # "INITIATIVE MEASURE 440" (the title's designation is "Measure",
    # so the badge reads as printed) and prints the choices "For" and
    # "Against". Nebraska prints no fiscal statement for a measure. The
    # pamphlet covers only the initiatives: Proposed Amendment No. 1,
    # the Legislature's, has its card drawn from the legislative
    # resolution that placed it on the ballot (LR19CA, whose Sec. 2
    # prints its ballot language), named as such.
    "ne": Ballot(guide="Informational Pamphlet on Initiative Measures "
                       "Appearing on the 2026 General Election Ballot",
                 fiscal_label=None,
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary",
                 badges={"Measure": "INITIATIVE MEASURE"},
                 guides={"ne-2026-11-03-amendment-1":
                         "Legislative Resolution 19CA"}),

    # West Virginia has no voter pamphlet. The Legislature's resolution
    # numbers and designates each amendment and summarises its purpose,
    # and the Secretary of State prints them in a "Public Notice"
    # ("Title of Amendment: “Amendment 1: ...”", "Summary of Purpose:"),
    # the same words the ballot prints over its choices "FOR" and
    # "AGAINST". The ballot heads it "Amendment No. 1" (designation()
    # skips the "No.", so the badge reads AMENDMENT). No fiscal
    # statement exists for it.
    "wv": Ballot(guide="Public Notice",
                 fiscal_label=None,
                 choices=("For", "Against"),
                 card_source_kind="official-title-summary"),

    # Kansas has no voter pamphlet. Its one official statement is the
    # ballot itself, the Secretary of State's "State of Kansas Official
    # General Election Ballot" for the amendment: the explanatory
    # statement and "A vote for / A vote against this proposition" lines
    # House Concurrent Resolution No. 5004 orders printed on it, the
    # question "Shall the following be adopted?", the amended section and
    # the choices "Yes" and "No". It prints no fiscal statement. The
    # ballot heads the amendment only "Constitutional Amendment", with no
    # number, so its card has no number and draws no badge.
    "ks": Ballot(guide="Official General Election Ballot",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Kentucky prints no voter guide, explanation or fiscal statement.
    # Under KRS 118.415 the General Assembly writes the ballot question
    # itself, and SB 10 (Acts Chapter 12) has the whole question and the
    # whole amended section printed on the ballot: the county sample
    # ballot ("CONSTITUTIONAL AMENDMENT 1", badge AMENDMENT, from the
    # title's designation) is the card's page. The ballot prints the
    # choices "YES" and "NO".
    "ky": Ballot(guide="Sample Ballot",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Indiana publishes no voter pamphlet. Its closest official
    # explanation is the Indiana Election Division's "2026 Indiana
    # Election Legislation Summary", written for election administrators:
    # each constitutional amendment's explanation, history and the ballot
    # text as the General Assembly prescribed it, headed "Public Question
    # #1" (the contest title drops the "#" so designation() finds
    # "Question"; badge QUESTION). It prints no fiscal statement, and the
    # ballot's choices are "Yes" and "No".
    "in": Ballot(guide="2026 Indiana Election Legislation Summary",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Vermont prints no voter guide and no explanation. Each town's
    # ballot carries an "OFFICIAL STATE CONSTITUTIONAL AMENDMENT BALLOT"
    # panel: "PROPOSAL 3" (badge PROPOSAL), "To see if the voters will
    # amend the Vermont Constitution by adding Article 23 to read:", the
    # article's text and the choices "YES" and "NO". The card quotes that
    # panel. No fiscal statement exists for a proposal the General
    # Assembly adopts.
    "vt": Ballot(guide="Official State Constitutional Amendment Ballot",
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


def guide_of(ballot: Ballot, contest_id: str) -> str:
    """The publication the card of contest `contest_id` is a page of: the
    state's guide, unless the entry names another for that contest."""
    return ballot.guides.get(contest_id, ballot.guide)


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
