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
    # text pdftotext sets inside a card's quote that the page prints
    # beside it, by contest id: a document footer, the ballot's "Yes" and
    # "No" boxes. Each is dropped wherever it stands as whole words in
    # that contest's card source before the verbatim check
    # (checks.check_card); every other contest's check is unchanged.
    card_strays: dict[str, tuple[str, ...]] = field(default_factory=dict)

    # the publication a measure's card is a page of where it is not the
    # guide (a measure the guide does not cover), by contest id
    guides: dict[str, str] = field(default_factory=dict)


BALLOTS: dict[str, Ballot] = {
    # A county measure's card is a page of its county's publication, not
    # the state's guide: San Diego's Voter Information Guide prints each
    # measure's ballot label and impartial analysis; Los Angeles prints
    # its ballot label only in the measure's proposed ordinance; Orange
    # County's Voter Information Guide prints each city measure's ballot
    # question, impartial analysis and arguments in its own section. San
    # Bernardino's guide prints no ballot question, which its cards quote
    # from the resolution placing the measure; the guide is still the
    # publication the measure's pages are in. Riverside's guide is titled
    # "County Voter Information Guide" on its pages, with no county name,
    # so its cards use that name as printed. Alameda's Composite Voter
    # Information Guide prints each measure's ballot question and
    # impartial analysis. Santa Cruz County posts each measure's
    # documents separately; its cards quote the ballot question from the
    # resolution placing the measure, and name the county's guide.
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
                     "ca-2026-11-03-santa-ana-measure-n":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-irvine-measure-d":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-orange-city-measure-i":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-orange-city-measure-j":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-orange-city-measure-k":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-costa-mesa-measure-c":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-westminster-measure-o":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-san-bernardino-county-measure-i":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-ontario-measure-h":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-chino-measure-f":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-chino-hills-measure-j":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-upland-measure-m":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-highland-measure-e":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-colton-measure-o":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-lake-forest-measure-f":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-newport-beach-measure-h":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-san-clemente-measure-m":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-placentia-measure-l":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-laguna-beach-measure-e":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-los-alamitos-measure-g":
                         "Orange County Voter Information Guide",
                     "ca-2026-11-03-pleasanton-measure-hh":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-union-city-measure-ii":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-newark-measure-dd":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-emeryville-measure-bb":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-dublin-unified-measure-i":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-san-lorenzo-unified-measure-j":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-sunol-glen-unified-measure-k":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-riverside-county-measure-a":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-hemet-measure-q":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-perris-measure-c":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-lake-elsinore-measure-t":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-banning-measure-u":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-banning-measure-v":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-banning-measure-w":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-san-bernardino-ccd-measure-y":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-san-bernardino-city-unified-measure-z":
                         "Board of Education Resolution No. 10.6",
                     "ca-2026-11-03-upland-unified-measure-a":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-barstow-ccd-measure-c":
                         "Board of Trustees Resolution, Appendix B",
                     "ca-2026-11-03-beaumont-unified-measure-b":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-sb-mountains-hospital-measure-q":
                         "San Bernardino County Voter Information Guide",
                     "ca-2026-11-03-rim-of-the-world-park-measure-r":
                         "Board of Directors Resolution No. 07132026.3",
                     "ca-2026-11-03-rancho-mirage-measure-r":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-canyon-lake-measure-e":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-indian-wells-measure-h":
                         "Riverside County Voter Information Guide",
                     "ca-2026-11-03-perris-union-high-measure-aa":
                         "County Voter Information Guide",
                     "ca-2026-11-03-hemet-unified-measure-i":
                         "County Voter Information Guide",
                     "ca-2026-11-03-temecula-valley-unified-measure-s":
                         "County Voter Information Guide",
                     "ca-2026-11-03-murrieta-valley-unified-measure-m":
                         "County Voter Information Guide",
                     "ca-2026-11-03-desert-recreation-measure-p":
                         "County Voter Information Guide",
                     "ca-2026-11-03-san-bernardino-ccd-measure-y-riverside":
                         "County Voter Information Guide",
                     "ca-2026-11-03-alameda-county-measure-rtm":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-oakland-measure-ee":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-oakland-measure-ff":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-hayward-measure-cc":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-alameda-measure-l":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-alameda-measure-m":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-alameda-measure-n":
                         "Alameda County Composite Voter Information Guide",
                     # San Francisco's Department of Elections prints
                     # each proposition's ballot question, digest and
                     # Controller's Statement, and Regional Measure RTM's
                     # ballot question and impartial analysis, in its
                     # Voter Information Pamphlet & Sample Ballot.
                     **{f"ca-2026-11-03-san-francisco-county-measure-{x}":
                        "San Francisco Voter Information Pamphlet & "
                        "Sample Ballot"
                        for x in ("rtm", "a", "b", "c", "d", "e", "f")},
                     # San Bernardino's guide prints no ballot question:
                     # these cards quote it from the city's resolution
                     "ca-2026-11-03-adelanto-measure-p":
                         "City of Adelanto Resolution No. 26-37",
                     "ca-2026-11-03-twentynine-palms-measure-g":
                         "City of Twentynine Palms Resolution No. 26-22",
                     "ca-2026-11-03-needles-measure-d":
                         "City of Needles Resolution No. 2026-29",
                     "ca-2026-11-03-needles-measure-k":
                         "City of Needles Resolution No. 2026-27",
                     "ca-2026-11-03-grand-terrace-measure-n":
                         "City of Grand Terrace Resolution No. 2026-21",
                     "ca-2026-11-03-needles-measure-l":
                         "City of Needles Ordinance 684-AC",
                     "ca-2026-11-03-albany-measure-o":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-albany-measure-p":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-albany-measure-q":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-albany-measure-r":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-albany-measure-s":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-albany-measure-t":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-piedmont-measure-gg":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-san-mateo-county-measure-rtm":
                         "Public Transit Revenue Measure District Resolution No. 2",
                     "ca-2026-11-03-san-mateo-county-measure-l":
                         "Resolution No. 081882",
                     "ca-2026-11-03-san-mateo-county-measure-aa":
                         "Resolution No. 081882",
                     "ca-2026-11-03-san-mateo-county-measure-j":
                         "Resolution No. 081882",
                     "ca-2026-11-03-san-mateo-county-measure-u":
                         "Resolution No. 081882",
                     "ca-2026-11-03-half-moon-bay-measure-i":
                         "Resolution No. 2026-39",
                     "ca-2026-11-03-half-moon-bay-measure-q":
                         "RESOLUTION NO. C-2026-63",
                     "ca-2026-11-03-brisbane-measure-x":
                         "RESOLUTION NO. 2026-28",
                     "ca-2026-11-03-portola-valley-measure-n":
                         "RESOLUTION NO. 3010-2026",
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
                     "ca-2026-11-03-pacifica-measure-bb":
                         "Resolution No. 61-2026",
                     "ca-2026-11-03-berkeley-measure-u":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-berkeley-measure-v":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-berkeley-measure-w":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-berkeley-measure-x":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-berkeley-measure-y":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-berkeley-measure-z":
                         "Alameda County Composite Voter Information Guide",
                     "ca-2026-11-03-berkeley-measure-aa":
                         "Alameda County Composite Voter Information Guide",
                     # San Mateo County posts each district measure's
                     # documents one by one, not as a pamphlet: these
                     # cards quote the ballot question from the board's
                     # resolution, named as its first page titles it
                     "ca-2026-11-03-san-mateo-community-college-measure-v":
                         "Resolution No. 26-25",
                     "ca-2026-11-03-jefferson-union-high-measure-m":
                         "Resolution No. 2025-2026/19",
                     "ca-2026-11-03-cabrillo-unified-measure-z":
                         "Resolution No. 09-2026",
                     "ca-2026-11-03-san-mateo-foster-city-measure-w":
                         "Resolution No. 06/25-26",
                     "ca-2026-11-03-burlingame-elementary-measure-r":
                         "Resolution No. 2025/2026-25",
                     "ca-2026-11-03-san-carlos-elementary-measure-k":
                         "Resolution No. 11:25/26",
                     "ca-2026-11-03-pacifica-school-measure-t":
                         "Resolution No. 2026-06-10-B",
                     # The City Clerk's own pamphlet prints each City of
                     # Los Angeles measure's ballot question, Impartial
                     # Summary and yes/no meanings.
                     **{f"ca-2026-11-03-los-angeles-measure-{x}":
                        "City of Los Angeles Voter Information Pamphlet"
                        for x in ("te", "la", "pl", "ee",
                                  "prk", "prt", "fd", "sc")},
                     # Sonoma County's Registrar of Voters publishes each
                     # measure's guide pages as one PDF headed "Local
                     # Ballot Measure: H"; no page naming the guide was
                     # archived, so the card names the pages as headed.
                     "ca-2026-11-03-sonoma-county-measure-h":
                         "Local Ballot Measure: H",
                     "ca-2026-11-03-santa-rosa-junior-college-measure-ab":
                         "Local Ballot Measure: AB",
                     "ca-2026-11-03-santa-rosa-measure-l":
                         "Local Ballot Measure: L",
                     "ca-2026-11-03-rohnert-park-measure-k":
                         "Local Ballot Measure: K",
                     "ca-2026-11-03-windsor-measure-i":
                         "Local Ballot Measure: I",
                     # Contra Costa County's guide could not be fetched:
                     # Measure RTM's card quotes Alameda County's copy of
                     # the District's ballot question and analysis
                     "ca-2026-11-03-contra-costa-county-measure-rtm":
                         "Alameda County Composite Voter Information Guide",
                     # and Clayton's cards quote the City Clerk's notice
                     "ca-2026-11-03-clayton-measure-m":
                         "Notice of Special Measure Election for the City of Clayton",
                     "ca-2026-11-03-clayton-measure-n":
                         "Notice of Special Measure Election for the City of Clayton",
                     # and Richmond's and Walnut Creek's cards quote the
                     # ballot question from the City Council's resolution
                     # placing the measure, named as its first page
                     # titles it
                     "ca-2026-11-03-richmond-measure-q":
                         "Resolution No. 143-26",
                     "ca-2026-11-03-walnut-creek-measure-u":
                         "Resolution Submitting a Measure to the Voters of Walnut Creek",
                     # Napa County's guide could not be fetched either:
                     # Measure B's card quotes the ballot question from
                     # the Board of Supervisors' resolution calling the
                     # election, named as its first page titles it
                     "ca-2026-11-03-napa-county-measure-b":
                         "Resolution of the Napa County Board of Supervisors",
                     # The Internet Archive's captures of the county
                     # guide's own pages for West Contra Costa Unified's
                     # Measure V and San Pablo's Measure S print each
                     # ballot question, impartial analysis and arguments
                     **{f"ca-2026-11-03-{slug}":
                        "Contra Costa County Voter Information Guide"
                        for slug in ("west-contra-costa-unified-measure-v",
                                     "san-pablo-measure-s")},
                     # and Acalanes Union High's card quotes the ballot
                     # question from the Governing Board's resolution,
                     # named as its first page titles it
                     "ca-2026-11-03-acalanes-high-measure-w":
                         "Resolution No. 26-27-01",
                     **{f"ca-2026-11-03-{x}":
                        "Santa Cruz County Voter Information Guide"
                        for x in ("santa-cruz-county-measure-d",
                                  "santa-cruz-county-measure-e",
                                  "scotts-valley-measure-g",
                                  "los-gatos-saratoga-measure-n")},
                     # Sacramento County issues each voter's guide through
                     # a portal; its Current Measure Information page
                     # prints each measure's ballot question, impartial
                     # analysis, full text, tax rate statement and
                     # arguments.
                     **{f"ca-2026-11-03-{slug}": "Current Measure Information"
                        for slug in ("los-rios-ccd-measure-h",
                                     "sacramento-city-unified-measure-m",
                                     "natomas-unified-measure-d",
                                     "center-joint-unified-measure-e",
                                     "galt-joint-union-high-measure-g",
                                     "folsom-measure-i",
                                     "folsom-measure-j",
                                     "folsom-measure-k",
                                     "galt-measure-l")},
                     # San Mateo city measures: the card is a page of the
                     # city's resolution that prints the ballot question,
                     # named as its first page titles it
                     "ca-2026-11-03-menlo-park-measure-p":
                         "Resolution No. 7008",
                     "ca-2026-11-03-burlingame-measure-d":
                         "Resolution No 104-2026",
                     "ca-2026-11-03-san-carlos-measure-g":
                         "Resolution No. 2026 – 088",
                     "ca-2026-11-03-east-palo-alto-measure-o":
                         "Resolution No. 57 – 2026",
                     "ca-2026-11-03-east-palo-alto-measure-cc":
                         "Resolution No. 30 - 2026",
                     "ca-2026-11-03-belmont-measure-y":
                         "Resolution No. 2026 – 69",
                     # Marin County's guide could not be archived: Marin's
                     # Measure AB card quotes Sonoma's pages, as Sonoma's
                     # does, and Sausalito's quotes the City Clerk's page,
                     # headed "Measure X (2026)".
                     "ca-2026-11-03-santa-rosa-junior-college-measure-ab-marin":
                         "Local Ballot Measure: AB",
                     "ca-2026-11-03-sausalito-measure-x":
                         "Measure X (2026)",
                     # San Joaquin County prints each measure's ballot
                     # question, impartial analysis, tax rate statement
                     # and arguments in its composite guide.
                     **{f"ca-2026-11-03-{slug}":
                        "County of San Joaquin Voter Information Guide & "
                        "Sample Ballot"
                        for slug in ("lodi-unified-measure-t",
                                     "lincoln-unified-measure-v",
                                     "escalon-unified-measure-u")},
                     # Napa County's guide could not be fetched: each Napa
                     # city's card quotes its ballot question from the
                     # city's own document, named as headed
                     "ca-2026-11-03-american-canyon-measure-p":
                         "Resolution No. 2026-57",
                     "ca-2026-11-03-st-helena-measure-s":
                         "Measure S - Ballot Question",
                     "ca-2026-11-03-yountville-measure-y":
                         "Yountville Town Council Staff Report",
                     # Placer County Elections posts each measure's guide
                     # pages as one PDF and no combined guide; the card
                     # names the PDF by its own head.
                     "ca-2026-11-03-rocklin-unified-measure-d":
                         "Measure D — School Bond Election – Rocklin "
                         "Unified School District",
                     "ca-2026-11-03-tahoe-truckee-unified-measure-p":
                         "Measure P — Education Parcel Tax Measure – Tahoe "
                         "Truckee Unified School District",
                     "ca-2026-11-03-south-placer-fire-measure-b":
                         "Measure B — South Placer Fire Protection District, "
                         "Fire and Emergency Medical Response Measure",
                     # Stanislaus County's Voter Information Guide prints
                     # each measure's impartial analysis, arguments and
                     # text but no ballot question: each card quotes it
                     # from the notice or resolution that prints it,
                     # named as headed
                     "ca-2026-11-03-modesto-city-high-measure-k":
                         "Notice of Election",
                     "ca-2026-11-03-sylvan-union-measure-n":
                         "Notice of Election",
                     "ca-2026-11-03-ceres-measure-p":
                         "Resolution No. 2026-79",
                     "ca-2026-11-03-riverbank-measure-m":
                         "Notice Fixing Time for Submission of Arguments "
                         "For or Against Measure M",
                     "ca-2026-11-03-patterson-measure-l":
                         "Notice of Election",
                     # El Dorado County prints each measure's full text,
                     # ballot question, arguments and impartial analysis
                     # in its Voter Information Pamphlet.
                     **{f"ca-2026-11-03-{slug}":
                        "El Dorado County Voter Information Pamphlet"
                        for slug in (
                            "el-dorado-county-measure-s",
                            "lynx-trail-road-zone-measure-a",
                            "walnut-drive-road-zone-measure-j",
                            "tegra-road-zone-measure-k",
                            "rancho-ponderosa-estates-road-zone-measure-l",
                            "fernwood-cothrin-ranch-road-zone-measure-m",
                            "garden-valley-ranch-measure-h",
                            "rolling-hills-measure-n",
                            "showcase-ranches-measure-q",
                            "golden-west-measure-r")},
                     # Solano County's printed guide was not archived; the
                     # Registrar posts each measure's filed documents, and
                     # each card quotes its ballot question from the
                     # resolution placing the measure, named as headed
                     "ca-2026-11-03-solano-county-measure-e":
                         "Resolution No. 2026-164",
                     "ca-2026-11-03-solano-county-measure-h":
                         "Resolution No. 2026-150",
                     "ca-2026-11-03-fairfield-measure-p":
                         "Resolution No. 2026-159",
                     "ca-2026-11-03-fairfield-measure-q":
                         "Resolution No. 2026-158",
                     "ca-2026-11-03-vacaville-measure-v":
                         "Resolution No. 2026-106",
                     "ca-2026-11-03-benicia-measure-x":
                         "Resolution No. 26-77",
                     "ca-2026-11-03-benicia-measure-y":
                         "Resolution No. 26-81",
                     "ca-2026-11-03-benicia-measure-z":
                         "Resolution No. 26-82",
                     "ca-2026-11-03-rio-vista-measure-o":
                         "Resolution No. 2026-033",
                     # Dixon Unified's question is its resolution's
                     # Appendix B, revised and refiled under that heading
                     "ca-2026-11-03-dixon-unified-measure-u":
                         "Abbreviated Form of Bond Measure",
                     # More Sonoma County measures, each headed as its
                     # pages are, as Sonoma's Measure H is.
                     **{f"ca-2026-11-03-{slug}": f"Local Ballot Measure: {x}"
                        for slug, x in (
                            ("windsor-unified-measure-j", "J"),
                            ("old-adobe-union-measure-o", "O"),
                            ("west-sonoma-county-union-high-measure-g", "G"),
                            ("waugh-measure-e", "E"),
                            ("harmony-union-measure-m", "M"),
                            ("coast-life-support-measure-d-sonoma", "D"),
                            ("schell-vista-measure-n", "N"))},
                     # Fresno County posts each measure's filed documents
                     # and no printed guide: each card quotes the ballot
                     # question from the resolution that prints it,
                     # named as headed
                     "ca-2026-11-03-coalinga-measure-j":
                         "Resolution No. 4337",
                     "ca-2026-11-03-firebaugh-measure-f":
                         "Resolution No. 26-46",
                     "ca-2026-11-03-orange-cove-measure-o":
                         "Resolution No. 2026-28",
                     "ca-2026-11-03-sanger-measure-b":
                         "Resolution No. 2026-72",
                     "ca-2026-11-03-fresno-county-measure-a":
                         "Resolution No. 26-257",
                     "ca-2026-11-03-fresno-measure-d":
                         "Resolution No. 2026-179",
                     "ca-2026-11-03-fresno-county-measure-s":
                         "Resolution No. 26-294",
                     "ca-2026-11-03-fowler-measure-t":
                         "Resolution No. 2854",
                     "ca-2026-11-03-sierra-kings-measure-h":
                         "Resolution No. 328",
                     # Nevada County Elections prints each local
                     # measure's ballot question, what your vote means,
                     # impartial analysis, arguments and full text in its
                     # Voter Information Guide.
                     **{f"ca-2026-11-03-{slug}":
                        "Nevada County Voter Information Guide"
                        for slug in ("nevada-city-measure-q",
                                     "pleasant-ridge-elementary-measure-m")},
                     # More Placer County measures, each named by its own
                     # PDF's head, as Rocklin Unified's Measure D is.
                     "ca-2026-11-03-placer-county-measure-g":
                         "Measure G — Proposal to Amend Placer County "
                         "Charter Section 206",
                     "ca-2026-11-03-placer-county-measure-h":
                         "Measure H — Proposal to Amend Placer County "
                         "Charter Section 502",
                     "ca-2026-11-03-roseville-measure-a":
                         "Measure A — Council Compensation Adjustment and "
                         "Inflation Limitation Measure",
                     "ca-2026-11-03-rocklin-measure-c":
                         "Measure C — 1/2% Transactions and Use (Sales) Tax",
                     "ca-2026-11-03-lincoln-measure-f":
                         "Measure F — Lincoln Public Safety/Taxpayer "
                         "Protection Measure",
                     # Yolo County Elections posts each local measure's
                     # ballot question, impartial analysis, full text and
                     # arguments as the material of its voter guide, which
                     # it calls the "County Voter Information Guide" (no
                     # cover page archived to confirm the county's name
                     # in the title). Los Rios H's Yolo contest quotes
                     # Sacramento County's page, as Sacramento's does.
                     **{f"ca-2026-11-03-{slug}":
                        "Yolo County Voter Information Guide"
                        for slug in ("yolo-county-measure-x",
                                     "davis-measure-w",
                                     "woodland-measure-y",
                                     "woodland-measure-z",
                                     "winters-unified-measure-b")},
                     "ca-2026-11-03-los-rios-ccd-measure-h-yolo":
                         "Current Measure Information",
                     # Madera County posts each measure's filed documents
                     # and no printed guide was found online: the county
                     # measure's card quotes the ballot question from the
                     # registrar's legal notice, named as the registrar
                     # titles it; each school bond's quotes the abbreviated
                     # form from the board's resolution, named as headed.
                     "ca-2026-11-03-madera-county-measure-u":
                         "Notice of Date Fixed for Submitting Arguments",
                     "ca-2026-11-03-yosemite-unified-measure-y":
                         "Resolution No. 2025/2026-20",
                     "ca-2026-11-03-alview-dairyland-measure-v":
                         "Resolution No. 26-27-02",
                     "ca-2026-11-03-yosemite-unified-sfid-1-measure-w":
                         "Resolution No. 2025/2026-19",
                     # Merced County's guide could not be fetched, so the
                     # City of Livingston's cards quote the City's own
                     # notice, headed "Measures to be Voted On"
                     **{f"ca-2026-11-03-{slug}": "Measures to be Voted On"
                        for slug in ("livingston-measure-t",
                                     "livingston-measure-u")},
                     # Merced County Elections posts each measure's ballot
                     # question, impartial analysis, full text, arguments
                     # and any tax rate statement on its page "November 3,
                     # 2026, General Election" and no printed guide, so
                     # these cards name that page
                     **{f"ca-2026-11-03-{slug}":
                        "November 3, 2026, General Election"
                        for slug in ("merced-measure-b",
                                     "los-banos-measure-v",
                                     "le-grand-union-high-measure-a",
                                     "los-banos-unified-measure-c")},
                     # Santa Barbara County Elections prints each local
                     # measure's impartial analysis, arguments, full text
                     # and (on its sample ballot pages) ballot question in
                     # its Voter Information Guide and Sample Ballot.
                     **{f"ca-2026-11-03-{slug}":
                        "Santa Barbara County Voter Information Guide"
                        for slug in ("isla-vista-measure-e",
                                     "isla-vista-measure-f")},
                     # Santa Barbara County Elections prints each local
                     # measure's impartial analysis, arguments, full text
                     # and sample ballot label in its guide, one PDF per
                     # ballot type.
                     **{f"ca-2026-11-03-{slug}":
                        "Santa Barbara County Voter Information Guide "
                        "and Sample Ballot"
                        for slug in ("santa-maria-measure-c",
                                     "carpinteria-measure-i",
                                     "guadalupe-measure-g",
                                     "guadalupe-measure-j",
                                     "santa-ynez-valley-measure-d",
                                     "allan-hancock-measure-h")},
                     # The Imperial County Registrar of Voters posts each
                     # measure's ballot question, full text, impartial
                     # analysis and any argument as one PDF; no
                     # countywide guide is posted, so each card names
                     # its measure's PDF as headed, as Placer's do.
                     "ca-2026-11-03-imperial-county-measure-s":
                         "Measure S — Imperial County Public Safety Sales "
                         "and Use Tax Initiative",
                     "ca-2026-11-03-imperial-valley-healthcare-measure-n":
                         "Measure N — Maintaining Local Hospitals and "
                         "Emergency Healthcare Services",
                     "ca-2026-11-03-el-centro-measure-t":
                         "Measure T — El Centro Public Safety/City "
                         "Services Measure",
                     "ca-2026-11-03-calexico-measure-o":
                         "Measure O — City of Calexico Public Safety "
                         "Sales Tax",
                     "ca-2026-11-03-meadows-elementary-measure-p":
                         "Measure P — Meadows Union Elementary School "
                         "District $1.8M Bond Measure",
                     "ca-2026-11-03-meadows-elementary-measure-q":
                         "Measure Q — Meadows Union Elementary School "
                         "District $2.2M Bond Measure",
                     "ca-2026-11-03-westmorland-elementary-measure-r":
                         "Measure R — Westmorland Union Elementary School "
                         "District Bond Measure",
                     # Humboldt County's Full Voter Information Guide
                     # prints each local measure's impartial analysis and
                     # arguments but no ballot question (its sample ballot
                     # pages are placeholders): each card quotes it from
                     # the resolution or appendix that prints it, named as
                     # headed
                     "ca-2026-11-03-eureka-measure-h":
                         "Resolution No. 2026-32",
                     "ca-2026-11-03-eureka-measure-i":
                         "Resolution No. 2026-42",
                     "ca-2026-11-03-arcata-measure-g":
                         "Resolution No. 256-63",
                     "ca-2026-11-03-fortuna-measure-d":
                         "Resolution No. 2026-12",
                     "ca-2026-11-03-ferndale-unified-measure-e":
                         "Abbreviated Form of Bond Measure",
                     # The San Luis Obispo County Clerk-Recorder prints
                     # each local measure's impartial analysis and
                     # arguments in its Voter Information Guide, one PDF
                     # per ballot type; where the guide does not print
                     # the ballot question, the card quotes it from the
                     # resolution or the city's notice page.
                     **{f"ca-2026-11-03-{slug}":
                        "San Luis Obispo County Voter Information Guide"
                        for slug in ("arroyo-grande-measure-c",
                                     "arroyo-grande-measure-d",
                                     "grover-beach-measure-f",
                                     "grover-beach-measure-a",
                                     "pismo-beach-measure-e",
                                     "paso-robles-unified-measure-g",
                                     "allan-hancock-measure-h-san-luis-obispo")},
                     # The Humboldt County Office of Elections prints each
                     # local measure's impartial analysis and arguments in
                     # its Full Voter Information Guide, and posts the
                     # district's resolution (with its ballot question) as
                     # a separate packet, which the cards quote.
                     **{f"ca-2026-11-03-{slug}":
                        "Full Voter Information Guide"
                        for slug in (
                            "southern-humboldt-healthcare-measure-k",
                            "shasta-tehama-trinity-jccd-measure-c-humboldt",
                            "ferndale-fpd-measure-f",
                            "petrolia-fpd-measure-j")},
                     # Mendocino County Elections posts each measure's
                     # guide pages; most print no ballot question, so
                     # each card quotes it from the page that does, named
                     # as headed: the resolution or exhibit that prints
                     # it, Point Arena's notice, Sonoma's pages for
                     # Measure D; AB's pages print it in its full text
                     "ca-2026-11-03-fort-bragg-measure-b":
                         "Resolution No. 5039-2026",
                     "ca-2026-11-03-point-arena-measure-c":
                         "Public Notice: Transient Occupancy Tax Measure",
                     "ca-2026-11-03-coast-life-support-measure-d":
                         "Local Ballot Measure: D",
                     "ca-2026-11-03-santa-rosa-jc-measure-ab-mendocino":
                         "Full Text of Measure AB",
                     "ca-2026-11-03-southern-humboldt-healthcare-measure-k-mendocino":
                         "Ballot Question/Abbreviated Form of Ballot Measure",
                     # Siskiyou County posts no voter guide, only a Notice
                     # of Election per measure: Tulelake Multi-County FPD
                     # I's card quotes the ballot question from the
                     # District's resolution, as posted by Modoc County,
                     # named as headed
                     "ca-2026-11-03-tulelake-fpd-measure-i":
                         "Resolution No. 2026-4",
                     # Lassen County Elections prints each local measure's
                     # impartial analysis, arguments, full text, ballot
                     # question (or, for Measure Z, ballot summary) and
                     # tax rate statement in its Local Voter Information
                     # Guide
                     **{f"ca-2026-11-03-{slug}":
                        "Local Voter Information Guide"
                        for slug in (
                            "lassen-union-high-measure-y",
                            "lassen-library-measure-z",
                            "shasta-tehama-trinity-jccd-measure-c-lassen")},
                     # Tehama County posts no voter guide, only each
                     # measure's filed documents: each card quotes the
                     # ballot question from the ordinance or resolution
                     # that prints it, named as headed
                     "ca-2026-11-03-tehama-county-measure-e":
                         "Ordinance No. 2158",
                     "ca-2026-11-03-red-bluff-measure-d":
                         "Resolution No. 21-2026",
                     "ca-2026-11-03-red-bluff-juhsd-measure-h":
                         "Resolution No. 2026.27-1",
                     "ca-2026-11-03-los-molinos-unified-measure-g":
                         "Resolution No. 6-18-26B",
                     "ca-2026-11-03-shasta-tehama-trinity-jccd-measure-c-tehama":
                         "Resolution No. 2025-26-18",
                     # Modoc County posts no voter guide, only each
                     # measure's documents: each card quotes the ballot
                     # question from the district's resolution or
                     # appendix that prints it, named as headed
                     "ca-2026-11-03-cal-pines-csd-measure-p":
                         "Resolution No. 2026-G",
                     "ca-2026-11-03-cal-pines-csd-measure-o":
                         "Resolution No. 2026-F",
                     "ca-2026-11-03-tulelake-fpd-measure-i-modoc":
                         "Resolution No. 2026-4",
                     "ca-2026-11-03-shasta-tehama-trinity-jccd-measure-c-modoc":
                         "Abbreviated Form of Bond Measure",
                     # Butte County Clerk-Recorder/Elections prints each
                     # local measure's ballot question, impartial analysis
                     # and arguments in its guide, titled "Local Voter
                     # Information Guide" with no county name
                     **{f"ca-2026-11-03-{slug}":
                        "Local Voter Information Guide"
                        for slug in ("oroville-measure-r",
                                     "oroville-measure-s",
                                     "oroville-city-elementary-measure-q")},
                     # The Lake County Registrar of Voters prints each
                     # local measure's ballot question, impartial
                     # analysis and arguments in its Voter's Pamphlet
                     **{f"ca-2026-11-03-{slug}": "Voter’s Pamphlet"
                        for slug in ("clearlake-measure-d",
                                     "middletown-unified-measure-c")},
                     # Trinity County Elections prints each local
                     # measure's ballot question, impartial analysis,
                     # arguments, full text and any tax rate statement in
                     # its Consolidated County Voter Information Guide
                     **{f"ca-2026-11-03-{slug}":
                        "Consolidated Trinity County Voter Information "
                        "Guide"
                        for slug in (
                            "shasta-tehama-trinity-jccd-measure-c-trinity",
                            "post-mountain-pud-measure-d")},
                     # The Calaveras County Clerk-Recorder / Registrar of
                     # Voters prints each local measure's impartial
                     # analysis (with the ballot question at its head),
                     # tax rate statement, arguments and full text in its
                     # Voter Information Pamphlet
                     "ca-2026-11-03-calaveras-unified-measure-a":
                         "Calaveras County Voter Information Pamphlet",
                     # Mono County Elections prints each local measure's
                     # ballot label (on its sample ballot pages), full
                     # text, impartial analysis, any tax rate statement
                     # and arguments in its Voter Information Guide and
                     # Sample Ballot, one PDF per ballot type
                     **{f"ca-2026-11-03-{slug}":
                        "Mono County Voter Information Guide and Sample "
                        "Ballot"
                        for slug in (
                            "eastern-sierra-unified-sfid-1-measure-o",
                            "mammoth-unified-measure-p")},
                     # Inyo County Elections does the same in its Voter
                     # Information Guide & Sample Ballot
                     **{f"ca-2026-11-03-{slug}":
                        "Inyo County Voter Information Guide & Sample "
                        "Ballot"
                        for slug in ("mesa-csd-measure-y",
                                     "lone-pine-fpd-measure-z")},
                     # Yuba County Elections posts each measure's ballot
                     # question, full text, impartial analysis, tax rate
                     # statement and arguments as one PDF naming no
                     # guide, so the card names it as headed, as
                     # Imperial's are
                     "ca-2026-11-03-plumas-lake-elementary-measure-h":
                         "Measure H — Plumas Lake Elementary School "
                         "District",
                     # The Santa Clara County Registrar of Voters posts
                     # each measure's letter, ballot question and vote
                     # threshold, with its impartial analysis and filed
                     # arguments, on its List of Local Measures page
                     **{f"ca-2026-11-03-{slug}":
                        "Santa Clara County Registrar of Voters, List of "
                        "Local Measures"
                        for slug in ("mountain-view-measure-e",
                                     "mountain-view-measure-f",
                                     "milpitas-measure-k",
                                     "cupertino-measure-l",
                                     "gilroy-measure-b",
                                     "morgan-hill-measure-a",
                                     "los-altos-measure-d")},
                     # The Santa Clara County Registrar of Voters posts
                     # each local measure's letter, ballot question and
                     # vote threshold on its List of Local Measures page,
                     # with the impartial analysis and arguments beside
                     # it; the cards quote the question from that page
                     **{f"ca-2026-11-03-{slug}":
                        "Santa Clara County Registrar of Voters, List of "
                        "Local Measures"
                        for slug in ("gilroy-unified-measure-m",
                                     "alum-rock-measure-o",
                                     "alum-rock-measure-p",
                                     "orchard-measure-r",
                                     "cambrian-measure-q",
                                     "el-camino-healthcare-measure-s")},
                     # Merced County Elections posts each measure's
                     # ballot question, impartial analysis, full text,
                     # tax rate statement and arguments on its "November
                     # 3, 2026, General Election" page (no printed guide
                     # archived); Kings County Elections posts Lemoore's
                     # ballot label, impartial analysis and resolution on
                     # its "Current Election Information" page. Each card
                     # names its county's page as titled.
                     **{f"ca-2026-11-03-{slug}":
                        "November 3, 2026, General Election"
                        for slug in (
                            "merced-union-high-sfid-1-measure-w",
                            "merced-union-high-sfid-2-measure-x",
                            "merced-union-high-sfid-3-measure-z")},
                     "ca-2026-11-03-lemoore-measure-p":
                         "Current Election Information",
                     # The Santa Clara County Registrar of Voters posts
                     # each measure's letter, ballot question and vote
                     # threshold, with its filed impartial analysis and
                     # arguments, on its List of Local Measures page
                     **{f"ca-2026-11-03-{slug}":
                        "Santa Clara County Registrar of Voters, List of "
                        "Local Measures"
                        for slug in ("santa-clara-county-measure-rtm",
                                     "palo-alto-measure-j",
                                     "santa-clara-measure-c",
                                     "sunnyvale-measure-g",
                                     "sunnyvale-measure-h",
                                     "sunnyvale-measure-i")},
                     # The County of Monterey Elections Department posts
                     # each local measure's letter, vote threshold and
                     # ballot question on its List of Local Measures page,
                     # linking each filed document (for a city's measure,
                     # a note that they are filed with the city clerk);
                     # the cards quote the question from that page
                     **{f"ca-2026-11-03-{slug}":
                        "County of Monterey Elections Department, List of "
                        "Local Measures"
                        for slug in (
                            "carmel-unified-measure-i",
                            "south-monterey-county-joint-union-high-measure-j",
                            "pacific-grove-unified-measure-k",
                            "santa-lucia-csd-measure-t",
                            "soledad-mission-recreation-measure-u",
                            "north-county-recreation-measure-v",
                            "monterey-county-measure-e",
                            "north-monterey-county-unified-measure-l",
                            "salinas-measure-g",
                            "salinas-measure-h",
                            "carmel-by-the-sea-measure-m",
                            "carmel-by-the-sea-measure-n",
                            "king-city-measure-p")},
                     # Shasta County Elections prints each local measure's
                     # pages in its guide, headed on its contest index
                     # "This is the County Voter Information Guide";
                     # Tuolumne County Elections prints Measure C in its
                     # Local Voter Information Guide
                     **{f"ca-2026-11-03-{slug}":
                        "County Voter Information Guide"
                        for slug in ("columbia-elementary-measure-d",
                                     "shasta-county-measure-e",
                                     "shasta-county-measure-f",
                                     "shasta-fpd-measure-g")},
                     "ca-2026-11-03-summerville-elementary-measure-c":
                         "Local Voter Information Guide",
                     # The Glenn County Elections Department prints
                     # Willows K's ballot question, ordinance, impartial
                     # analysis and fiscal analysis in its General
                     # Election Voter Information Guide; Sutter County
                     # Clerk-Recorder/Elections prints each measure's
                     # ballot question, full text, analysis and arguments
                     # in its County Voter Information Pamphlet; Amador
                     # County Elections posts each measure's question,
                     # analysis and arguments on its "2026 General
                     # Election" page, which every cited file comes from,
                     # so those cards name the page as titled, as
                     # Merced's do
                     "ca-2026-11-03-willows-measure-k":
                         "General Election Voter Information Guide",
                     **{f"ca-2026-11-03-{slug}":
                        "County Voter Information Pamphlet"
                        for slug in ("sutter-county-measure-g",
                                     "live-oak-unified-measure-h")},
                     **{f"ca-2026-11-03-{slug}": "2026 General Election"
                        for slug in ("sutter-creek-measure-r",
                                     "amador-county-measure-s")},
                     # Kern County Elections posts each measure's
                     # documents (the resolution with its ballot
                     # question, any impartial analysis and arguments)
                     # on its page "November 3, 2026, General Election",
                     # which every cited county file comes from, so these
                     # cards name the page as titled, as Merced's do
                     **{f"ca-2026-11-03-{slug}":
                        "November 3, 2026, General Election"
                        for slug in ("arvin-measure-h",
                                     "delano-measure-k",
                                     "delano-measure-l",
                                     "delano-measure-m",
                                     "mcfarland-measure-n",
                                     "mcfarland-measure-o",
                                     "mcfarland-measure-p",
                                     "shafter-measure-q")},
                     # Kern County Elections posts each local measure's
                     # filed documents (the resolution or full text with
                     # its ballot question, the impartial analysis and
                     # the arguments) on its page "November 3, 2026,
                     # General Election", and no printed guide was
                     # archived, so these cards name that page
                     **{f"ca-2026-11-03-{slug}":
                        "November 3, 2026, General Election"
                        for slug in ("tehachapi-unified-measure-d",
                                     "lost-hills-union-measure-e",
                                     "california-city-measure-j",
                                     "bear-valley-csd-measure-r",
                                     "bear-valley-csd-measure-s",
                                     "kern-county-measure-z")},
                     # The Los Angeles County Registrar-Recorder/County
                     # Clerk's list "Measures Appearing on the Ballot"
                     # prints each local measure's letter, vote threshold
                     # and ballot question, which these cards quote
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County Clerk,"
                        " Measures Appearing on the Ballot"
                        for slug in ("bellflower-unified-measure-sm",
                                     "baldwin-park-measure-cr",
                                     "glendora-unified-measure-g",
                                     "claremont-unified-measure-cs",
                                     "hacienda-la-puente-unified-measure-b")},
                     # The Los Angeles County Registrar-Recorder/County
                     # Clerk's list "Measures Appearing on the Ballot"
                     # prints each local measure's letter, vote threshold
                     # and ballot question; these cards quote it
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Measures Appearing on the Ballot"
                        for slug in ("culver-city-measure-aa",
                                     "culver-city-measure-t",
                                     "culver-city-measure-yv",
                                     "redondo-beach-measure-art",
                                     "south-pasadena-measure-sos",
                                     "south-el-monte-measure-cl",
                                     "south-el-monte-measure-rm")},
                     # The Los Angeles County Registrar-Recorder/County
                     # Clerk prints each local measure's letter, vote
                     # threshold and ballot question, and who filed its
                     # arguments, in its list "Measures Appearing on the
                     # Ballot"; the cards quote the question from it
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Measures Appearing on the Ballot"
                        for slug in ("santa-monica-measure-es",
                                     "santa-monica-measure-gg",
                                     "santa-monica-measure-rr",
                                     "santa-monica-measure-vv",
                                     "santa-monica-measure-tt",
                                     "hermosa-beach-measure-hb",
                                     "south-gate-measure-sg",
                                     "lynwood-measure-l")},
                     # Los Angeles County's city measures quote their
                     # ballot question from the Registrar-Recorder/County
                     # Clerk's list "Measures Appearing on the Ballot"
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Measures Appearing on the Ballot"
                        for slug in ("rancho-palos-verdes-measure-rs",
                                     "carson-measure-cu",
                                     "huntington-park-measure-hp",
                                     "paramount-measure-p",
                                     "pasadena-measure-pfd",
                                     "diamond-bar-measure-q",
                                     "san-marino-measure-u")},
                     # These cards, too, quote the ballot question from the
                     # Registrar-Recorder/County Clerk's list "Measures
                     # Appearing on the Ballot"
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Measures Appearing on the Ballot"
                        for slug in ("bell-gardens-measure-w",
                                     "whittier-measure-ev",
                                     "whittier-measure-el",
                                     "burbank-measure-c",
                                     "burbank-measure-cd",
                                     "el-segundo-measure-ct",
                                     "san-gabriel-measure-ps",
                                     "hawaiian-gardens-measure-bl",
                                     "cudahy-measure-ok",
                                     "cudahy-measure-h",
                                     "palos-verdes-estates-measure-pve")},
                     # Los Angeles County's school district measures quote
                     # their ballot question from the Registrar-Recorder/
                     # County Clerk's list "Measures Appearing on the
                     # Ballot"
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Measures Appearing on the Ballot"
                        for slug in ("keppel-union-measure-k",
                                     "hawthorne-school-measure-hh",
                                     "valle-lindo-school-measure-r",
                                     "charter-oak-unified-measure-s",
                                     "el-rancho-unified-measure-ed",
                                     "temple-city-unified-measure-tcs",
                                     "san-marino-unified-measure-sms",
                                     "las-virgenes-unified-measure-lv")},
                     # The staged excerpt of that list misreads a figure
                     # in Inglewood Unified MM's question, so its card
                     # quotes the question from the measure's full text in
                     # the Registrar's Interactive Sample Ballot
                     "ca-2026-11-03-inglewood-unified-measure-mm":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Interactive Sample Ballot",
                     # The same list prints these city measures' letters,
                     # vote thresholds and ballot questions, which their
                     # cards quote
                     **{f"ca-2026-11-03-{slug}":
                        "Los Angeles County Registrar-Recorder/County "
                        "Clerk, Measures Appearing on the Ballot"
                        for slug in ("hawthorne-measure-o",
                                     "palmdale-measure-de",
                                     "rosemead-measure-rc",
                                     "alhambra-measure-ht",
                                     "alhambra-measure-db",
                                     "monterey-park-measure-hom",
                                     "monterey-park-measure-aaa",
                                     "burbank-measure-cc")},
                 },
                 # pdftotext runs the ordinance's document footer into the
                 # middle of Needles L's question, and the resolution's
                 # ballot boxes into Grand Terrace N's and California
                 # City J's; it reads the bullets of Benicia Z's question
                 # as an "x" each
                 card_strays={
                     "ca-2026-11-03-benicia-measure-z": ("x",),
                     "ca-2026-11-03-california-city-measure-j":
                         ("YES", "NO"),
                     "ca-2026-11-03-grand-terrace-measure-n":
                         ("Yes", "No"),
                     "ca-2026-11-03-needles-measure-l":
                         ("09960 00000\\45188769.I",),
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

    # Wisconsin prints no voter guide. The Wisconsin Elections Commission's
    # "Type A Notice of Referendum" for the election prints each question
    # the Legislature submits, "QUESTION 1: “Partial veto. Shall ...?”"
    # (badge QUESTION, from the title's designation): its title and
    # question, the words the ballot prints over the choices "Yes" and
    # "No". It prints no "yes means" lines and no fiscal statement, and
    # none exists for a joint resolution.
    "wi": Ballot(guide="Type A Notice of Referendum",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Minnesota prints no voter guide. The Secretary of State's
    # "Constitutional amendments" page prints the ballot's instructions,
    # the amendment's title and question as the ballot prints them, its
    # choices "Yes" and "No", and the amended section, and no fiscal
    # statement (there is no fiscal note for the law that proposes it).
    # The page numbers no amendment, so the card has no
    # number and draws no badge.
    "mn": Ballot(guide="Constitutional amendments",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Missouri has no voter pamphlet. The Secretary of State's "2026
    # Ballot Measures" page prints each measure's designation ("Amendment
    # 3", "Proposition A"; the badge is the title's designation), its
    # Official Ballot Title (the question, then the State Auditor's fiscal
    # note summary under no heading of its own) and its Fair Ballot
    # Language ('A "yes" vote will ...', 'A "no" vote will ...'). The
    # Auditor's fiscal note heads that paragraph "Fiscal Note Summary".
    # Its Fair Ballot Language names the two votes "yes" and "no".
    "mo": Ballot(guide="2026 Ballot Measures",
                 fiscal_label="Fiscal Note Summary",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # Tennessee has no voter pamphlet. The Secretary of State's page
    # "2026 Proposed Constitutional Amendments" prints, for each
    # "Constitutional Amendment #1" (the contest title drops the "#" so
    # designation() finds "Amendment"; badge AMENDMENT), the resolutions
    # that proposed it, the Attorney General's Summary, the Question,
    # the lines 'A "yes" vote is a vote to ...' and 'A "no" vote ...',
    # and the choices "Yes" and "No". It prints no fiscal statement; the
    # Fiscal Review Committee's fiscal note heads its own "FISCAL
    # IMPACT:". No card quotes it, so the heading is never drawn. The
    # archived page is a browser snapshot that sets each resolution's
    # link target in brackets after its name; the strays drop them, so
    # the card's origin quotes the line as the page prints it.
    "tn": Ballot(guide="2026 Proposed Constitutional Amendments",
                 fiscal_label="FISCAL IMPACT:",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary",
                 card_strays={
                     "tn-2026-11-03-amendment-1": (
                         "[https://publications.tnsosfiles.com/acts/113/"
                         "resolutions/sjr0919.pdf]",
                         "[https://publications.tnsosfiles.com/acts/114/"
                         "resolutions/sjr0025.pdf]"),
                     "tn-2026-11-03-amendment-2": (
                         "[https://publications.tnsosfiles.com/acts/113/"
                         "resolutions/hjr0081.pdf]",
                         "[https://publications.tnsosfiles.com/acts/114/"
                         "resolutions/sjr0001.pdf]"),
                     "tn-2026-11-03-amendment-3": (
                         "[https://publications.tnsosfiles.com/acts/113/"
                         "resolutions/hjr0094.pdf]",
                         "[https://publications.tnsosfiles.com/acts/114/"
                         "resolutions/sjr0009.pdf]"),
                 }),

    # Michigan mails no voter pamphlet. Its Bureau of Elections posts
    # "2026 November ballot questions" (the PDF's own title): each
    # proposal's designation ("Proposal 2026-1"), heading, question and
    # the choices "[ ] Yes" and "[ ] No", with no "yes means" lines and
    # no fiscal statement. The Senate and House Fiscal Agencies call the
    # proposals "Proposal 26-1" and "Proposal 26-2" (badge PROPOSAL,
    # from the title's designation). The Senate Fiscal Agency's analysis
    # heads its fiscal statement "Fiscal Impact"; no card quotes it, so
    # the heading is never drawn.
    "mi": Ballot(guide="2026 November ballot questions",
                 fiscal_label="Fiscal Impact",
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary"),

    # New Hampshire prints no voter guide. The Secretary of State's
    # "Questions on the General Election Ballot 2026" prints each
    # question as the ballot does, numbered "1." and "2." under its
    # heading ("Questions Relating to Constitutional Amendments proposed
    # by the 2026 General Court"; "Statutory Question required by HB
    # 1300, ..."), with the choices "Yes" and "No" (badge QUESTION, from
    # the title's designation). It prints no "yes means" lines, no short
    # titles and no fiscal statement. Question 2 breaks "three-fifths" at
    # a line's end, which pdftotext joins, so a card quote may lose that
    # hyphen (card_column_breaks); the sheet has one column.
    "nh": Ballot(guide="Questions on the General Election Ballot 2026",
                 fiscal_label=None,
                 choices=("Yes", "No"),
                 card_source_kind="official-title-summary",
                 card_column_breaks=True),
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
