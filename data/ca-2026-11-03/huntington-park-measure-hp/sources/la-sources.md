# City of Huntington Park — Measure HP: sources

Measure HP: establish a lifetime limit of two terms for City Council members.
Election: November 3, 2026 (consolidated with the Gubernatorial General Election).
All files retrieved 2026-10-30.

## Files in this directory

| File | Publisher | Title | URL | Retrieved | Pages kept | Scan/text | Note |
|---|---|---|---|---|---|---|---|
| `resolution.pdf` | LA County Board of Supervisors (supporting document, originated by the City of Huntington Park City Clerk) | City Clerk's Aug 6, 2026 transmittal letter requesting consolidation of the City's Nov 3, 2026 municipal election with the Statewide General Election | https://file.lacounty.gov/SDSInter/bos/supdocs/221467.pdf | 2026-10-30 | 24 of 42 | Mixed scan/text with small embedded images | Originally `measure-hp-resolution.pdf`. **The source PDF bound two complete copies of the same packet back to back** (confirmed: pages 1–24 and pages 25–42 are the same content, down to repeated DocuSign envelope IDs). Trimmed to the first complete copy (pages 1–24) with `qpdf`, then recompressed (`--object-streams=generate --compress-streams=y`); 2.2MB → ~1.9MB, with the duplicate half removed rather than shrunk. It's a bundle, not a single document type: it contains, bound together, Resolution No. 2026-25 (submitting the term-limits measure to voters), Resolution No. 2026-28 (calling the election, requesting consolidation), Ordinance No. 2026-06 (full text of the term-limits ordinance), the Ballot Measure Question exhibit, the Impartial Analysis, and blank/procedural forms (Request for Measure Information, Letter Designation Form). Closest single fixed-vocabulary fit is `resolution.pdf` since the resolutions anchor the packet, but it also serves as the full-text and impartial-analysis source for this measure. |
| `measure-page.html` | City of Huntington Park (hpca.gov) | "Learn About Measure HP" | https://hpca.gov/908/Learn-About-Measure-HP | 2026-10-30 | n/a (HTML) | Text | Originally `measure-hp-page.html`. Scrubbed of session identifiers with `scrub-html.sh`. |

Finder note (from the earlier research pass): both URLs were located via web search. No blocked sites were encountered.

## County measure list entry

From `county-measure-list-excerpt.txt` (LA County RR/CC final measures list):

> HP Shall an ordinance be adopted to establish a lifetime limit of two (2) terms for members of the City Council, where a partial term of more than two (2) years counts as a full term, and a partial term of two (2) years or less does not count against the limit?
>
> Supporters: Eduardo Martinez, Mayor, City of Huntington Park; Nancy Martiz, Council Member, City of Huntington Park
> Opponents: None submitted.

Vote threshold: Majority 50%+1 (the packet's "Request for Measure Information" form has the city's checkbox marked "Majority of Votes Cast (50% + 1)").

## What's present vs. missing

- **Impartial analysis**: present, inside `resolution.pdf` — by Andrew Sarega, City Attorney of Huntington Park (outside counsel, Sarega Law).
- **Argument in favor**: **missing — not found/not fetched.** The transmittal letter's table of contents lists "Argument in Favor" as enclosure #6, and the county list names two supporters (Mayor Eduardo Martinez, Council Member Nancy Martiz), but the actual argument text is **not present** in the packet — it jumps directly from the Impartial Analysis to the procedural forms. Not found on the city's "Learn About Measure HP" page either (not deeply mined beyond confirming the measure exists).
- **Argument against**: **missing — not filed.** The RR/CC list states "Opponents: None submitted," so no argument against exists to find.
- **Rebuttal to argument for / rebuttal to argument against**: **not applicable/not found.** A "Ballot Label Arguments & Rebuttals Form" is listed in the transmittal letter's table of contents but not present in the scanned packet — likely a blank procedural form, or no rebuttal was filed since no opposing argument exists (opponents: none submitted).
- **Full text**: present, inside `resolution.pdf` — Ordinance No. 2026-06, amending Huntington Park Municipal Code Title 2, Ch. 9, §2-9.03.
- **Tax rate statement / fiscal**: **not applicable.** This is a governance/term-limits measure with no direct cost; no fiscal analysis was found or appears to exist.
