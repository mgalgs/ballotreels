# City of Monterey Measure S — sources

Jurisdiction: City of Monterey voters. Special tax (street infrastructure), two-thirds vote. Retrieved 2026-10-28 with plain GETs.

| File | Publisher | Title | URL |
|---|---|---|---|
| `city-news-letter-assigned.html` | City of Monterey | News release, Aug 18, 2026: "Monterey's Street Repair Extension Measure Officially Assigned Ballot Letter by County Elections" | https://monterey.gov/news_detail_T39_R130.php | (not staged in the repo: the page carries nothing beyond the ballot question and letter)

**Missing (needs manual download):** ballot question as printed, full text of the ordinance, City Attorney impartial analysis, arguments/rebuttals. The county elections site blocks plain GETs; the city's "monterey.gov/fixingstreets" page (named in the release as holding the full text) returned an empty redirect to the fetcher. The ballot question in the README is from the finder and is **not** confirmed by an official record.

## Quoted facts (city news release)

- **Letter:** "The Monterey County Elections Department has officially assigned ballot letter "S" to the City of Monterey's proposed Continuation of Street Infrastructure Rehabilitation tax. Listed as Measure S on the upcoming November 3, 2026, general municipal ballot".
- **Threshold, rate, term:** "If approved by a two-thirds majority of city voters voting on the measure, Measure S will extend the existing special one-cent per dollar transactions and use tax for eight additional years, changing the expiration date from March 31, 2027, to March 31, 2035."
- **No rate increase:** "Because the measure continues the existing rate established by voters under Measure P (2014) and Measure S (2018), it will not increase current tax rates. It is projected to generate approximately $12 million annually".
- **Use:** "all revenues from Measure S must be deposited into a dedicated special fund and can only be spent on repairing and rehabilitating Monterey's street infrastructure."
- (The release also quotes City Manager Dante Hall on a "$12 million structural budget deficit" — that is the city's advocacy-adjacent statement, not neutral analysis; use with care.)

## Feed documents retrieved 2026-10-30

```
City of Monterey Measure S -- special 1-cent transactions and use tax continuation, 8 years (2/3 vote)
Retrieved 2026-10-30 with safe-http-get.sh.

STATUS: FOUND (no minutes). Signed Resolution No. 26-103 C.S. (July 21, 2026, roll call 5-0, full ordinance as
Exhibit A), the City Attorney's impartial analysis, both primary arguments and both rebuttals. No minutes or
agenda-system record was found: monterey.gov/agendas only 301-redirects (no body; the Wayback capture was empty),
there is no July 21 entry on the "Meeting Recap" page, and no Legistar/Granicus/PrimeGov client exists for the city.

Source page: City of Monterey City Clerk "Elections" page, section "Measure S on the Ballot":
  https://monterey.gov/your_city_hall/city_clerk/elections.php
  "On July 21, 2026, the City Council adopted Resolution No. 26-103 C.S., placing ballot measure S on the
   November 3, 2026 ballot."
Links on monterey.gov redirect to files.monterey.gov; the URLs fetched are below.

FILES

resolution-26-103-cs.pdf
  URL:  https://files.monterey.gov/Document-Center/City-Hall/City-Clerk/Elections/2026/26-103%20Continuation%20of%20Special%20Taxations%20and%20Use%20Tax.pdf
  What: Signed Resolution No. 26-103 C.S. with the ballot question ("CONTINUATION OF STREET INFRASTRUCTURE
        REHABILITATION TAX. Without increasing tax rates, shall the ...") and Exhibit A, the full ordinance
        (Ordinance No. ____ C.S., blanks to be filled if voters approve). "PASSED AND ADOPTED BY THE COUNCIL OF THE
        CITY OF MONTEREY this 21st day of July, 2026"; AYES 5 (Barber, Garcia, Rasch, Smith, Williamson), NOES 0,
        ABSENT 0. Notes that the resolution must pass by two-thirds of the council (Rev. & Tax. Code 7285.9).
        Text layer present.
  Meeting date: July 21, 2026.

impartial-analysis.pdf
  URL:  https://files.monterey.gov/Document-Center/City-Hall/City-Clerk/Elections/2026/Measure-S-City-Attorney-impartial-analysis-2026.pdf
  What: City Attorney's impartial analysis of Measure S.

argument-in-favor.pdf (2 pp.)
  URL:  https://files.monterey.gov/Document-Center/City-Hall/City-Clerk/Elections/2026/Primary-Argument-In-Favor-of-Measure-S.pdf
argument-against.pdf (2 pp.)
  URL:  https://files.monterey.gov/Document-Center/City-Hall/City-Clerk/Elections/2026/FINAL-Primary-Argument-Against-Measure-S.pdf
rebuttal-to-argument-in-favor.pdf (2 pp.)
  URL:  https://files.monterey.gov/Document-Center/City-Hall/City-Clerk/Elections/2026/Rebuttal-to-argument-in-favor.pdf
rebuttal-to-argument-against.pdf (2 pp.)
  URL:  https://files.monterey.gov/Document-Center/City-Hall/City-Clerk/Elections/2026/Rebuttal-to-argument-against.pdf
  What: Primary arguments and rebuttals as filed with the City Clerk (posted Aug 21, 2026).

NOTES
- The README's earlier note that the Measure S ballot question was "not confirmed by an official record" is now
  resolved: the question is in Resolution 26-103 C.S.
- Adoption proof is the signed resolution with its roll call. Minutes were not found.
```
