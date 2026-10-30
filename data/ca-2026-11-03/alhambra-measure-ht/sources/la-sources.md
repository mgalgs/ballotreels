# City of Alhambra Measure HT: sources

Measure HT: Transient occupancy tax modernization (no rate increase; extends to short-term rentals)
Election: November 3, 2026 (consolidated with the Gubernatorial General Election)
All files retrieved 2026-10-30.

## Source documents

| File | Publisher | Title | URL | Retrieved | Pages kept/total | Scan or text | Note |
|---|---|---|---|---|---|---|---|
| `resolution.pdf` | City of Alhambra | Resolution R2M26-20 — City Council resolution requesting LA County consolidate the Measure HT election into Nov. 3, 2026 | https://www.alhambraca.gov/DocumentCenter/View/8184 | 2026-10-30 | 7/7 | scan, no text layer | Original filename `measure-ht-resolution.pdf`. Downsampled to grayscale/120dpi (as part of an 836KB combined batch with Measure DB's resolution; two input files 754KB+868KB -> 836KB total output). Consolidation-request resolution; does not itself carry the ballot question or ordinance text (those are in the files below). |
| `impartial-analysis.docx` | City of Alhambra (City Attorney) | City Attorney's impartial analysis of Measure HT (TOT modernization) | https://www.alhambraca.gov/DocumentCenter/View/8178/Impartial-Analysis-TOT---Ballot-Measure | 2026-10-30 | n/a | text (native .docx) | Kept as .docx; no `.pdf` conversion tool (libreoffice/soffice) was available in this environment. |
| `full-text.doc` | City of Alhambra | Ordinance No. O2M26-4865 (calling the TOT measure election), attaching the operative text as Ordinance No. O2M26-4866, Exhibit A — amends Alhambra Municipal Code Ch. 5.70 to broaden the "hotel" definition to include short-term rentals and extend the "transient" stay window from 21 to 30 days; no rate change | https://www.alhambraca.gov/DocumentCenter/View/8179/O2M26-4865-Ordinance-Calling-TOT-Measure-Election | 2026-10-30 | n/a | text (legacy .doc, Word 2007+ could not re-save it; original Office "Composite Document" format) | Kept as .doc (original format); no conversion tool available. Confirmed readable via `strings`/`pandoc` text extraction — contains "ORDINANCE NO. O2M26-4865", the ballot question, and the Section 1-2 TOT definition amendments. |

## Ballot question and supporters/opponents (verbatim, from the county's final measures list)

> Modernization/No Tax Rate Increase Measure. To maintain city services, such as: Fire protection, paramedic, 911 emergency response, crime prevention and keeping streets, infrastructure, and parks safe and well-maintained shall City of Alhambra's measure modernizing the hotel/motel transient occupancy tax be adopted at the current 12% rate for stays up to 30 days to include short-term lodging, providing an additional $134,000 annually for city services until ended by voters, with all money locally controlled?
>
> Supporters: Alhambra Firefighters Association; Alhambra Police Officers Association
>
> Opponents: None submitted.

Vote threshold: Majority Vote 50%+1. Council placed it on the ballot July 27, 2026.

## What's present and what's missing

- **Full ordinance text**: present (`full-text.doc`, Ordinance No. O2M26-4866, Exhibit A to Ordinance O2M26-4865).
- **Impartial analysis**: present (`impartial-analysis.docx`).
- **Resolution requesting consolidation**: present (`resolution.pdf`, R2M26-20).
- **Arguments for/against and rebuttals as filed**: not located as standalone documents. The city posted a procedural notice of the Aug. 13, 2026 filing deadline and a plain-language FAQ for both Alhambra measures, but neither contains the filed argument text (and the FAQ is explicitly excluded by this batch's rule against staging campaign/FAQ material as an argument file); not staged.
- **Fiscal analysis/staff report** beyond the revenue estimate already in the ballot question and the impartial analysis: not located.

## Registrar's Interactive Sample Ballot documents (added 2026-10-30)

Publisher: Los Angeles County Registrar-Recorder/County Clerk. Source: the Interactive Sample Ballot's contest data, https://isb.lavote.gov/parsed/4348/contests/bmc10940.json (English text of each statement, saved as HTML; the source URL and statement id are in a comment at the top of each file). Retrieved 2026-10-30. These are the documents the Registrar prints for the measure in the sample ballot, so they supersede any 'missing' note above for the same document.

- `impartial-analysis.html`
