# County documents — Le Grand Union High School District Measure A (GO bond)

Publisher: Merced County Elections (Registrar of Voters), via a browser fetch of the county's November 3, 2026 General Election page on 2026-10-29 (the page returns a Cloudflare 403 to a plain GET). Page: "November 3, 2026, General Election" — https://www.countyofmerced.com/4299/November-3-2026-General-Election. Retrieved 2026-10-29.

This resolves the earlier README's "ballot question NOT YET CONFIRMED" for Measure A — nothing had been archived for this measure before this fetch.

## Files

| File | Original name/URL | Pages kept (of total) | Scan or text | Note |
|---|---|---|---|---|
| `county-ballot-question.pdf` | MEASURE-A — https://www.countyofmerced.com/DocumentCenter/View/53618/MEASURE-A | 1 of 1 | text | |
| `county-full-text.pdf` | Full-Text_Eng — https://www.countyofmerced.com/DocumentCenter/View/53671/Full-Text_Eng | 6 of 6 | **scan, no text layer** | `pdftotext` extracts 0 characters. Rendered page 1 reads "Exhibit A... Full Text of Bond Measure." Grayscale/120dpi pass (`shrink-gray.sh`) produced a larger file than the Chrome-fetched original (575KB vs 502KB, likely because the source is an efficiently-compressed bitonal scan), so the original is kept per the shrink script's own smaller-of-the-two rule. |
| `county-impartial-analysis.pdf` | Impartial-Analysis-Eng — https://www.countyofmerced.com/DocumentCenter/View/53674/Impartial-Analysis-Eng | 1 of 1 | text | Generic filename on the county page ("Impartial-Analysis-Eng"), identified as Measure A's by its position in the page's Measure A section. |
| `county-argument-for.pdf` | Argument-in-Favor-of-Measure-A--Merced_County_Signature_Form---LeGrandUHSD-8-10-2026 — https://www.countyofmerced.com/DocumentCenter/View/53672/Argument-in-Favor-of-Measure-A--Merced_County_Signature_Form---LeGrandUHSD-8-10-2026 | 1 of 1 | **scan, no text layer** (only the two signature lines extract as text; `pdftotext` yields 77 characters) | Single page already — nothing to trim. Grayscale/120dpi pass produced the same size as the original, so the original is kept. |
| `county-measure-list.pdf` | List-of-Ballot-Measures-for-November-3-2026-General-Election (CFMR004, Registrar of Voters, printed 8/7/2026) — https://www.countyofmerced.com/DocumentCenter/View/53380/List-of-Ballot-Measures-for-November-3-2026-General-Election | 4 of 4 | text | Full countywide list; same file copied into every Merced measure dir staged in this round. |

## Not filed / not applicable

- Argument against: none filed. The county's "List of Ballot Measures" report shows only an argument in favor for Measure A.
- Rebuttals: none filed.
- Tax rate statement: not found on the county page for Measure A (the other Merced bond measures — C, W, X, Z — each have one; A does not appear to).
- Spanish-language versions also exist (SP-MEASURE-A_Ballot-Question, SP-Impartial-Analysis-Eng, Measure-A-SP-Full-Text, Measure-A-Argumento-a-favor-de-la-Medida) but were not fetched; only English copies are staged.
