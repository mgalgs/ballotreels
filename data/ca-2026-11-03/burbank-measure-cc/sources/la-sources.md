# City of Burbank Measure CC: sources

Measure CC: Charter amendment — removes the at-large election requirement for City Council, permits the City's electoral system to be set by ordinance or voter initiative
Election: November 3, 2026 (consolidated with the Gubernatorial General Election)
All files retrieved 2026-10-28.

## Source documents

| File | Publisher | Title | URL | Retrieved | Pages kept/total | Scan or text | Note |
|---|---|---|---|---|---|---|---|
| `resolution.pdf` | LA County Board of Supervisors (supporting document) | Letter from Kimberley Clark, Elections Official/Burbank City Clerk, to the LA County RR/CC requesting consolidation, enclosing a certified copy of City of Burbank Resolution No. 26-29,725 (Charter Amendment Measure, now lettered CC), with the full charter-amendment text attached as Exhibit A | https://file.lacounty.gov/SDSInter/bos/supdocs/221461.pdf | 2026-10-28 | 9/21 | scan with an embedded OCR text layer | Original filename `bos-supdoc-221461.pdf` (21 pp., also covers Measures C, CD and the consolidation resolution — not staged here). Trimmed with `qpdf` to pages 1-9 (cover letter + Resolution 26-29,725 + Exhibit A + certification), then downsampled to grayscale/120dpi: original 11.4MB (21 pp.) -> trimmed 5.0MB (9 pp.) -> grayscale 1.6MB. The grayscale step drops the OCR text layer; chosen anyway to keep this public repo's file sizes consistent with the rest of the batch (every other scanned document here lands under ~1MB). |

## Ballot question and supporters/opponents (verbatim, from the county's final measures list)

> CHARTER AMENDMENT MEASURE CC: Shall the Burbank City Charter be amended to remove the requirement for at-large elections of City Council members and permit the City's electoral system to be specified by ordinance adopted by the City Council or by the voters by initiative?
>
> Supporters: Burbank City Council
>
> Opponents: None submitted.

Vote threshold: Majority Vote 50%+1 (Resolution 26-29,725 §6: "if a majority of the votes cast ... are in favor ... the Measure shall be approved").

## What's present and what's missing

- **Full charter-amendment text**: present (`resolution.pdf`, Exhibit A, p. 8 of the trimmed file — amends Charter Article 3 §§300, 305 to remove "elected from the City at-large" language and let the electoral system be set by ordinance).
- **Resolution placing the measure on the ballot**: present (Resolution No. 26-29,725).
- **Impartial analysis, arguments/rebuttals, Measure C's own resolution/text**: all blocked. `burbankca.gov` returns HTTP 403 (Cloudflare) on every direct GET tried, including the exact URLs a web search confirmed exist for: Measure C's and CC's impartial analyses, Measure CC's argument in favor, and Resolution 26-29,718 (likely Measure C's resolution, not confirmed). No mirror of these was found on `content.lavote.gov`, `file.lacounty.gov`, or any other official host.
- **Measure C (City Services, TOT 10%->12%)** is not staged in this directory or elsewhere in this batch — it is out of scope for this pass (only CC and CD were assigned) and its own resolution/text were never obtained (see above).
- **Measure CD (By-District Council Elections)** was evaluated from the same source file and **not staged**: Resolution No. 26-29,726's text (pp. 10-15 of the original 21-page document) references its own Exhibit A ("the proposed Measure submitted to the voters is attached in Exhibit A") but the file jumps directly from the resolution's signature/certification page to "EXHIBIT B" (Map 130, the district map) — Exhibit A itself is absent from this copy, confirmed both by text search (`grep` for "EXHIBIT A" near Resolution 726: no match) and by rendering the page images at that boundary. Without the ordinance text, Measure CD fails this batch's gate (ballot question + the measure's own text) and was left out; see the batch-level report for the same conclusion.

## Registrar's Interactive Sample Ballot documents (added 2026-10-30)

Publisher: Los Angeles County Registrar-Recorder/County Clerk. Source: the Interactive Sample Ballot's contest data, https://isb.lavote.gov/parsed/4348/contests/bmc10942.json (English text of each statement, saved as HTML; the source URL and statement id are in a comment at the top of each file). Retrieved 2026-10-30. These are the documents the Registrar prints for the measure in the sample ballot, so they supersede any 'missing' note above for the same document.

- `full-text.html`
- `impartial-analysis.html`
