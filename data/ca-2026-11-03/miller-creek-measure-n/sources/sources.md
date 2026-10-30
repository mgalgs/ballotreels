# Miller Creek School District — Measure N

Sources gathered 2026-10-30.

county-measure-list.html: the county's list of measures (Wayback copy, 2026-10-09).
marin-bos-2026-09-08-consolidation-staff-report-26-4515.pdf: Marin County Registrar of Voters, Board of Supervisors staff report
26-4515 (Sept 8, 2026), https://marin.granicus.com/MetaViewer.php?view_id=33&event_id=4262&meta_id=1474983,
listing every Nov 3, 2026 measure's letter, jurisdiction and vote required.

## Marin County Elections measure page, read 2026-10-30

county-page.txt: the county's page for Measure N (also prints the tax rate statement). Read in a desktop Chrome browser (marincounty.gov returns
403 to scripted fetches) and saved as text; the file's header gives the URL and how
the text was taken. It prints the ballot question, the vote required, the impartial
analysis, the argument in favor (or 'No argument in favor ... was filed.') and the
argument against (or 'No argument against ... was filed.'), as on the county's site.

county-full-text.txt: the county's 'Full text of Measure N' page (the bond measure: findings,
accountability requirements, Bond Project List), read and saved the same way.
millercreeksd-localfunding.html: the District's own local-funding page (district material).

```
Measure N — Miller Creek (Elementary) School District — $67,000,000 GO bond (Prop 39, 55%)
Retrieved 2026-10-30. STATUS: PARTIAL — existence, amount and Board vote confirmed by official sources;
ballot question only from a secondary source; NO resolution/full text and NO minutes obtained.

millercreeksd-localfunding.html   (OFFICIAL — district)
  URL: https://www.millercreeksd.org/localfunding
  Publisher: Miller Creek School District. "Information on Measure N" + "Measure N FAQ". States the Board
  "voted unanimously to place Measure N, a $67 million school improvement bond, on the November 3, 2026,
  ballot"; "would levy $30 per $100,000 of assessed (not market) value"; 55% threshold. No ballot
  question, no resolution, no meeting date.
  FETCH NOTE: the site's TLS chain ends at Let's Encrypt "ISRG Root YR", which is not in this machine's
  trust store, so a plain GET fails (curl error 60). It works with
  `safe-http-get.sh --cacert <bundle>` where the bundle = /etc/ssl/certs/ca-certificates.crt plus the
  "Root YR" cert from http://yr.i.lencr.org/ (cross-signed by ISRG Root X1).

marin-bos-2026-09-08-consolidation-staff-report-26-4515.pdf   (OFFICIAL — county listing)
  URL: https://marin.granicus.com/MetaViewer.php?view_id=33&event_id=4262&meta_id=1474983
  Marin County Registrar of Voters, BOS staff report 26-4515 (Sept 8, 2026): "Measure N: Miller Creek
  School District (requires 55% approval)".

_secondary-localnewsmatters-marin.html   (SECONDARY — news site, not official)
  URL: https://localnewsmatters.org/marin-county-november-3-2026-2/ (also Wayback 20261016072544)
  Prints the ballot questions for all Marin measures; its O and AA wording matches the official district
  documents exactly. Measure N as printed there (line ~731):
    "Miller Creek Elementary School District Classroom Repair/ Upgrade Measure. To improve aging local
    elementary/middle schools by fixing bathrooms, plumbing, roofs, HVAC, and electrical systems;
    upgrading classrooms to support high quality math, science, technology, reading, writing, arts/music
    instruction; and improve school security/ student safety, shall Miller Creek Elementary School
    District's measure be adopted authorizing $67,000,000 in bonds at legal rates, with levies averaging
    $28 per $100,000 assessed value ($3,800,000 annually) while bonds are outstanding, independent
    oversight, audits and all funds locally controlled?"
  (Note the question says levies AVERAGING $28/$100k; the district page says up to $30/$100k.)

_campaign-home.html, _campaign-faq.html   (NOT OFFICIAL — "Yes on N" campaign committee)
  URLs: https://yesonnformillercreekschools.org/ , https://yesonnformillercreekschools.org/faq.html
  Kept only because the FAQ links the district's Simbli board portal (a 2023 Facilities Master Plan PDF).

NOT FOUND
  - Board resolution ordering the election (Exhibit A ballot question, full text/project list, tax rate
    statement) and the minutes of the meeting that adopted it.
    Route tried: district board portal is Simbli, https://simbli.eboardsolutions.com/Index.aspx?S=36030762
    (linked from the district site). SB_MeetingListing.aspx?S=36030762 returns an Imperva/Incapsula bot
    challenge to a plain GET. Not reachable without a browser.
  - County pages (Cloudflare 403; no Wayback snapshots):
    .../list-measures-110326/measure-n-110226 (note the "110226" slug)
    .../list-measures-110326/measure-miller-creek-school-district-110226/measure-n-full-text-110326
  - Impartial analysis and arguments.
```
