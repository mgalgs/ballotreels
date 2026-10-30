# City of Diamond Bar — Measure Q: sources

Measure Q: a 1¢ local general transactions and use (sales) tax for emergency response/Sheriff protection, wildfire preparedness, roads, and general city services.
Election: November 3, 2026 (consolidated with the Gubernatorial General Election).
All files retrieved 2026-10-30.

## Files in this directory

| File | Publisher | Title | URL | Retrieved | Pages kept | Scan/text | Note |
|---|---|---|---|---|---|---|---|
| `resolution.pdf` | City of Diamond Bar (City Council / City Clerk Kristina Santana) | Resolution No. 2026-28, "Proposing and Submitting to the Voters... a Proposal to Adopt an Initiative Ordinance Establishing a One Percent Transactions and Use Tax" — includes the full ballot question, vote-threshold section, and the complete ordinance text as the attached exhibit | https://www.diamondbarca.gov/DocumentCenter/View/14106/Resolution-Submitting-One-Percent-Sales-Tax-Measure-to-Diamond-Bar-Voters---November-2026-Election | 2026-10-30 | 15 of 15 | Full-page scan (CCITT) with OCR text | Originally `measure-q-resolution.pdf`. Grayscale/120dpi-shrunk; negligible change (1,425,649 → 1,346,879 bytes) since the source was already a low-resolution (72dpi) bilevel scan. Text layer verified intact. Also serves as the full-text source (the ordinance is the resolution's exhibit). Adopted July 21, 2026, vote 4-1 (Teng dissenting). |
| `impartial-analysis.pdf` | City of Diamond Bar (City Attorney) | "Impartial Analysis of Measure Q from Diamond Bar City Attorney," signed by Omar Sandoval | https://www.diamondbarca.gov/DocumentCenter/View/14209/Impartial-Analysis-of-Measure-Q-from-Diamond-Bar-City-Attorney | 2026-10-30 | 1 of 1 | Text | Originally `measure-q-ia.pdf`. No embedded images; kept as-is. |
| `staff-report.pdf` | City of Diamond Bar (city staff, for City Council) | "Agenda Item #: 9.1, Meeting Date: July 21, 2026 — City Council Agenda Report," recommending adoption of Resolution 2026-28, with fiscal/revenue-estimate and implementation-cost figures, plus the resolution/ordinance as attachments | https://www.diamondbarca.gov/DocumentCenter/View/14086/July-21-2026-Staff-Report-to-City-Council-on-Proposed-Transactions-and-Use-Tax | 2026-10-30 | 19 of 19 | Text with one small embedded image | Originally `measure-q-staff-report.pdf`. Kept as-is — no shrinking needed. |

**Not kept:** the source directory also had `measure-q-text.pdf`, described by the earlier research pass as "the full text of the measure... same PDF" as the resolution. An md5 check confirmed it is **byte-identical** to `measure-q-resolution.pdf` (now `resolution.pdf`) — not a separate extract, just a second copy of the same file under a different name. Dropped as a duplicate.

Finder note (from the earlier research pass): all URLs came from web search results, both direct `DocumentCenter` hits and the city's `/152/Election-Information` page. No blocked sites were encountered; the city's newsflash/FAQ pages render as JS single-page-app shells with a plain GET and were not usable, but that is a fetch-method limitation, not a block.

## County measure list entry

From `county-measure-list-excerpt.txt` (LA County RR/CC final measures list):

> Q To maintain local funding for emergency response/Sheriff protection; keep Diamond Bar's neighborhoods/public areas safe/clean; prevent property crimes/burglaries; minimize the risk of wildfires; prepare for/respond to wildfires/other natural disasters; maintain roads/prevent potholes; for other general city services; shall a measure be adopted establishing a 1¢ sales tax, providing approximately $6,000,000 annually until ended by voters, requiring audits/spending disclosure, all funds benefiting Diamond Bar residents?
>
> Supporters: Jody Roberto; Devang Mehta
> Opponents: None submitted.

Vote threshold: Majority 50%+1 (Resolution 2026-28 §2; the earlier research pass flagged the PDF's OCR text layer as slightly garbled on this exact clause — worth a visual spot-check of `resolution.pdf` page ~4 if precision matters).

## What's present vs. missing

- **Impartial analysis**: present (`impartial-analysis.pdf`).
- **Argument in favor**: **missing — not found/not fetched, and not confirmed either way whether one was filed.** Resolution 2026-28 §§10-12 set an August 14, 2026 deadline for direct arguments (well before the Oct 30, 2026 retrieval date), and the county list names two supporters, but the filed text was not found on the city's dedicated Measure Q page or its Election Information page (which lists the filing *deadline*, not the filed document). County-side sources (`content.lavote.gov`, `file.lacounty.gov`) were not checked for this measure.
- **Argument against**: **missing — not filed**, per the RR/CC list ("Opponents: None submitted").
- **Rebuttal to argument for / rebuttal to argument against**: **missing — not confirmed either way.** An August 24, 2026 deadline for rebuttals exists per Resolution 2026-28, but whether anything was filed is unconfirmed (same search-budget limitation as the argument in favor).
- **Full text**: present, inside `resolution.pdf` — the ordinance adding Chapter 3.14 to Title 3 of the Diamond Bar City Code.
- **Tax rate statement / fiscal**: present, inside `staff-report.pdf` — ~$6,000,000/year revenue estimate, ~$160,000 implementation/administration cost (already in the adopted FY2026-27 budget), and backing detail on the city's structural deficit (~$1M in FY2026-27, growing to ~$5M by 2030 and ~$12M by 2035) and General Fund reserves (~$29.9M).
