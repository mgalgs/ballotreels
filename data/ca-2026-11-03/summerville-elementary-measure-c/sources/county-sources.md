# Tuolumne County Elections documents (retrieved 2026-10-29)

Publisher: Tuolumne County Elections. The county's own site returns a Cloudflare
challenge to a plain GET; these pages are from the official Nov 3, 2026 Local Voter
Information Guide fetched via a browser session (`local-voter-information-guide.pdf`,
42pp, real text layer). It is a combined countywide guide covering several local
contests besides this measure; only Measure C's own pages are kept here.

Measure C's documents run together across consecutive pages with no blank
separators, so several files below share a page with their neighbor; the shared page
is kept in both files.

| file | original | pages kept (of total) | scan or text | note |
|---|---|---|---|---|
| `county-ballot-question.pdf` | `local-voter-information-guide.pdf`, p.25 (of 42) | 1 | text | includes the "For and Against" byline box |
| `county-full-text.pdf` | same, pp.26-32 | 7 | text | ends at "Severability" |
| `county-tax-rate-statement.pdf` | same, pp.33-34 | 2 | text | p.34 shared with impartial analysis's start |
| `county-impartial-analysis.pdf` | same, pp.34-36 | 3 | text | p.34 shared with tax rate statement's end; p.36 shared with argument-for's start |
| `county-argument-for.pdf` | same, pp.36-37 | 2 | text | p.36 shared with impartial analysis's end; p.37 shared with argument-against |
| `county-argument-against.pdf` | same, p.37 | 1 | text | the page reads "No argument against was filed." — shares the page with argument-for's end |
| `county-resolution.pdf` | `summerville-esd-bond-resolution.pdf` (district board resolution placing the measure on the ballot) | 13 (of 13) | scan, no text layer | already compact; `shrink-gray.sh` kept the original (grayscale re-encode was not smaller) |
| `county-measure-list.pdf` | same guide, p.2 | 1 | text | the guide's "Receiving Two Guides" page, listing local contests; "Bond Measure C" is the only local measure named (alongside non-measure local contests: Yosemite CCD trustee area 1, Tuolumne Utilities District Division 1, Groveland CSD) |

No argument against Measure C was filed — stated explicitly on the page itself — and
no rebuttal exists. `notice-of-bond-measure-c.pdf` (the county's "Notice of School
Bond Election") was also fetched but not staged here: it repeats the same ballot
question plus procedural filing deadlines, nothing not already covered above.
