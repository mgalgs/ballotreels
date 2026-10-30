# County documents — City of Lemoore Measure P (transient occupancy tax, 8% to 12%)

Publisher: Kings County Elections (Administration dept.), via a browser fetch of the county's "Current Election Information" page on 2026-10-29 (the page returns an Akamai 403 to a plain GET). Page: "Current Election Information | Kings County" — https://www.countyofkingsca.gov/departments/administration/elections/current-election-information. Retrieved 2026-10-29.

No repo dir existed for this measure before this fetch; nothing had been officially archived (the earlier README's leads were all blocked or stale).

## Files

| File | Original name/URL | Pages kept (of total) | Scan or text | Note |
|---|---|---|---|---|
| `county-ballot-question.pdf` | "Ballot Label - Measure P" — https://www.countyofkingsca.gov/home/showpublisheddocument/41998/639258375798370000 | 1 of 1 | text | EN/ES. |
| `county-impartial-analysis.pdf` | "Impartial Analysis - Measure P" — https://www.countyofkingsca.gov/home/showpublisheddocument/41788/639238494991570000 | 1 of 1 | text | EN/ES. States explicitly: "No Arguments For or Against were filed for this measure" (and the Spanish equivalent). |
| `county-full-text.pdf` | "Transient Occupancy Tax Resolution - Measure P" — https://www.countyofkingsca.gov/home/showpublisheddocument/41308/639203361902130000 | 8 of 8 | **scan, no text layer** | Filename/title says "resolution"; it is actually **Resolution No. 2026-22** of the Lemoore City Council (received-stamped by Kings County Elections Jul 9, 2026). Filed as `county-full-text.pdf` rather than `county-resolution.pdf` because the resolution's Section 4 approves "Ordinance 2026-XX, the City of Lemoore Transient Occupancy Tax Ordinance of 2026" as "Attachment A" inside this same PDF — there is no separate full-text/ordinance document, so this file serves as both the council resolution and the measure's full legal text. `pdftotext` extracts 0 characters (rendered page 2 shows the boxed ballot question, matching the ballot label verbatim). Grayscale/120dpi pass (`shrink-gray.sh`) shrank it from 2.9MB to 959KB; the shrunk copy is staged. |
| `county-measure-list.html` | "Current Election Information" page itself, its "Measures Submitted to the Voters" section — https://www.countyofkingsca.gov/departments/administration/elections/current-election-information | whole page | html | Lists only the City of Lemoore under "Measures Submitted to the Voters" — confirms Measure P is Kings County's only local measure for this election. |

## Not filed / not applicable

- Arguments for/against: **none filed** — stated explicitly in the impartial analysis itself, not inferred.
- Rebuttals: none (no arguments were filed to rebut).
- Tax rate statement: not applicable — a general tax (TOT rate increase), not a bond.
- Also fetched but not staged (not per-measure documents): `lemoore-notice-of-measure.pdf` (Notice of Measure to be Voted On, repeats the ballot question and gives the Aug 3, 2026 argument-filing deadline), `notice-of-election-related-activities.pdf` (countywide calendar, no measure content), `avenal-notice-of-special-election.pdf` (confirms Avenal has no measure, only two Council seats), and the 24 `vig/*.pdf` by-ballot-type voter guides (8 of them — ballot types 1–7 and 27 — repeat Measure P's ballot label and impartial analysis verbatim; none add new content; searching all 24 confirmed no other Kings County measure exists for this election, including a false lead for a "Measure H" that is actually a previously-passed Hanford measure cited only in two candidates' biographical statements).
