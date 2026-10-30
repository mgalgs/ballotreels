# City of San Marino — Measure U: sources

Measure U: "San Marino Service Preservation Measure" — extend the city's existing 6% utility users tax (UUT), for police, fire, paramedic, street/infrastructure, and youth/senior programs.
This is the **City of San Marino's** measure, distinct from the unrelated San Marino Unified School District's "Measure SMS" on the same ballot.
Election: November 3, 2026 (consolidated with the Gubernatorial General Election).
All files retrieved 2026-10-30.

## Files in this directory

| File | Publisher | Title | URL | Retrieved | Pages kept | Scan/text | Note |
|---|---|---|---|---|---|---|---|
| `staff-report.pdf` | City of San Marino (City Manager Philippe Eskandar, for City Council) | July 8, 2026 staff report, "SUBJECT: CONSIDERATION OF RESOLUTION NO. R-26-28..." | https://cms9files.revize.com/cityofsanmarino/City%20Clerk/elections/StaffReport_CONSIDERATION%20OF%20RESOLUTION%20NO.%20R-26-28.pdf | 2026-10-30 | 38 of 38 | Text/photo mix with OCR text | Originally `measure-u-staff-report.pdf`. **Note on the earlier research pass's description**: it called this a "303-pp. City Council agenda packet"; `pdfinfo` confirms the actual saved file is **38 pages**, and a header-string check (`SUBJECT:`, `RESOLUTION NO. R-26-28`, `ORDINANCE NO. O-26-1427`, `ARGUMENT IN FAVOR`) found no unrelated agenda items inside it — it is already a clean, self-contained excerpt covering just this item (staff report + Resolution R-26-28 + Ordinance O-26-1427 full text + the filed Argument in Favor), not a bloated full packet. No page trimming was needed. Grayscale/120dpi-shrunk (2.6MB → ~593KB); text layer verified intact. This single file is the source for the resolution, the full ordinance text, and the favor argument — it doesn't cleanly map to one fixed-vocabulary name, so `staff-report.pdf` (its primary identity) was used. |
| `measure-page.html` | City of San Marino | "Measure U: San Marino Service Preservation Measure Info" / Utility Users Tax Information page (FAQ, UUT history, comparison to neighboring cities, Town Hall notice) | https://sanmarinoca.gov/government/elections/utility_users_tax_information.php | 2026-10-30 | n/a (HTML) | Text | Originally `measure-u-page.html`. Scrubbed of session identifiers. |
| `elections-index-page.html` | City of San Marino | "2026 November Election Information" page | https://sanmarinoca.gov/government/elections/index.php | 2026-10-30 | n/a (HTML) | Text | Originally `measure-u-elections-index.html`. **Does not fit the fixed-name vocabulary** — a general elections-index page, not solely about this measure; kept its own descriptive name since `measure-page.html` was used for the dedicated UUT/Measure U page above. Scrubbed of session identifiers. |

Finder note (from the earlier research pass): the UUT info page URL was located via web search; the staff-report PDF link was found by reading that page's HTML, and required following a `sanmarinoca.gov` → `cms9files.revize.com` redirect. No blocked sites were encountered.

## County measure list entry

From `county-measure-list-excerpt.txt` (LA County RR/CC final measures list):

> U SAN MARINO SERVICE PRESERVATION MEASURE. To maintain existing funding which supports essential San Marino services including: police, fire, paramedic, emergency preparedness, repairing streets and sidewalks and other City infrastructure, providing youth and senior programs, and general government use; shall the City of San Marino measure be adopted extending the currently existing utility users tax at a rate of 6 percent, raising $2,620,000 annually, until ended by voters?
>
> Supporters: Mayor Chou; Vice Mayor Lo; Council Member Shepherd Romey; Council Member Chang; Council Member Chou
> Opponents: None submitted.

Vote threshold: Majority 50%+1 (this is a general-purpose tax renewal, not a special tax).

## What's present vs. missing

- **Impartial analysis**: **missing — not found/not fetched.** Resolution R-26-28 (inside `staff-report.pdf`) directs the City Attorney to prepare one (not to exceed 500 words), but the finished analysis document was not located as a standalone file.
- **Argument in favor**: present, inside `staff-report.pdf` — titled "VOTE YES ON MEASURE _" (the measure letter was not yet filled in on this draft copy; unsigned in this version).
- **Argument against**: **missing — not filed**, consistent with the RR/CC list naming only the five City Council members as proponents and no opponents, but no official "none submitted" notice was located to independently confirm this.
- **Rebuttal to argument for / rebuttal to argument against**: **missing — not found, consistent with none filed.** Same caveat as above: plausible given no opposing argument, but not independently confirmed by an official notice.
- **Full text**: present, inside `staff-report.pdf` — Ordinance No. O-26-1427, amending San Marino Municipal Code Chapter 26, Article 03 (the Utility Tax Ordinance).
- **Tax rate statement / fiscal**: the $2,620,000/year estimate is captured in the ballot question and in the staff report's background section (UUT first adopted 1992 via Ord. No. O-92-1028, renewed by voters three times since, reduced from 6% to 5% in 2015; current 5% UUT expires March 31, 2027). No separate fiscal/tax-rate-statement document was found beyond this.

## Registrar's Interactive Sample Ballot documents (added 2026-10-30)

Publisher: Los Angeles County Registrar-Recorder/County Clerk. Source: the Interactive Sample Ballot's contest data, https://isb.lavote.gov/parsed/4348/contests/bmc10957.json (English text of each statement, saved as HTML; the source URL and statement id are in a comment at the top of each file). Retrieved 2026-10-30. These are the documents the Registrar prints for the measure in the sample ballot, so they supersede any 'missing' note above for the same document.

- `argument-for.html`
- `impartial-analysis.html`
