# City of Coronado Measure D: sources

Measure D: raise the height limit for multiple-family developments in the R-4 Multiple-Family Residential Zone from 3 stories / 35 feet to 4 stories / 42 feet
Election: November 3, 2026 (consolidated with the Gubernatorial General Election)
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide, **ballot type 318**, PDF title "November 3 2026 General - San Diego" | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-318.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | City of Coronado | City website (City Clerk election pages) | https://www.coronado.ca.us/ |

**S3 is blocked.** Every GET to www.coronado.ca.us (home page, `/government/departments/city-clerk/elections`, `/151/Elections`) returned HTTP 403 with a Cloudflare "Attention Required!" challenge page, saved as `../../raw/coronado-home-HTTP403.html`. I did not try to get past it. The council resolution placing Measure D on the ballot and any City Clerk postings are **not archived**; see "Needs manual download" in the county README.

Ballot type 318 is a Coronado precinct (SanGIS *Election_Precinct_2026_11_03* layer, attribute `bt`; finder only). S1 confirms Measure D is on it.

Page numbers: "PDF p." is the page in S1. The printed footer ("SD 318-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig318-p44-sample-ballot-page.pdf` | S1, PDF p. 44 | Sample ballot page with Measure D |
| `vig318-p76-ballot-label-impartial-analysis-argument-against.pdf` | S1, PDF p. 76 (SD 318-074) | Ballot label, vote threshold, impartial analysis, argument against |
| `vig318-p77-full-text.pdf` | S1, PDF p. 77 (SD 318-075) | Full text of Measure D |
| `composite-ballot-p20.pdf` | S2, PDF p. 20 | Ballot as printed, with letter |

## Facts and the passages that establish them

### Ballot question

S1 PDF p. 76:

> MEASURE D
> Shall the measure, increasing the permissible height of "multiple-family developments" in the City of Coronado's R-4 Multiple Family Residential Zone from the existing maximum of 3 stories (with a maximum height of no more than 35 feet) to a maximum of 4 stories (with a maximum height of no more than 42 feet), be adopted?

### Vote required

S1 PDF p. 76: "This measure requires Simple Majority (50%+1) of those voting on the measure." The analysis adds: "Measure D will be approved if it receives a simple majority of "Yes" votes."

### Who votes on it

The guide prints Measure D under the heading "CITY OF CORONADO". The full text begins "THE PEOPLE OF THE CITY OF CORONADO DO ORDAIN AS FOLLOWS:" and the analysis refers to "voter consideration". **No fetched document states the electorate in words** (the council resolution, on the blocked City site, would). Unconfirmed beyond "voters of the City of Coronado" as implied.

### Who placed it on the ballot, and why

S1 PDF p. 76 (impartial analysis):

> The City Council of the City of Coronado placed Measure D on the ballot for voter consideration at the November 3, 2026, election.

> As part of the City's Sixth Cycle Housing Element Update adoption ("Housing Element Update"), the California Department of Housing and Community Development ("HCD") took the position that the Existing Height Limit constitutes a constraint on developments seeking to obtain the permitted density of 40 dwelling units per acre. ... As a result, the Housing Element Update contains Program H.1.F that requires the City to submit Measure D to the voters.

The resolution number, date and council vote are not in S1.

### Impartial analysis

S1 PDF p. 76, "IMPARTIAL ANALYSIS", signed "Johanna N. Canlas, City Attorney, City of Coronado". Key statements:

> Coronado Municipal Code ("CMC") Section 86.56.048 and Section B-2 of Part B of Chapter V of the Orange Avenue Corridor Specific Plan ("OACSP") currently limit the height of multiple-family developments in the R-4 Multiple-Family Residential Zone ("R-4 Zone") to a maximum building height of three stories with a maximum 35-foot height limit ("Existing Height Limit").

> per HCD's guidance, a zoning district must allow at least one story and 10 feet of height for every 10 dwelling units per acre of density allowed. In other words, the R-4 Zone's density of 40 dwelling units per acre must correspond with a height limit no lower than 4 stories and 40 feet and HCD has expressed that 42 feet is preferred to avoid constraining the density.

> If approved, Measure D would revise the height limits in both the CMC 86.56.048 and the OACSP pertaining to multiple family developments in the R-4 Zone so that the maximum building height is four stories but no more than 42 feet.

> A "Yes" vote is a vote in favor of Measure D, which is a vote in favor of revising the height limits as stated above. "No" vote is a vote against Measure D, which is a vote against revising the height limits as stated above.

### Arguments and rebuttals

- **Argument in favor**: **none printed.** S1 has no argument in favor of Measure D and no printed notice that none was filed.
- **Argument against**, S1 PDF p. 76. First line: "For over fifty-four years, Coronado voters sought to protect the village character of our City. Measure D asks residents to give that protection away." It says "Since 1972, Proposition R has capped affected building heights in that zone at three stories" and that "in 2023 the City signed a settlement agreement under threat of $100,000 monthly fines and loss of local zoning authority." Signer: Kevin Shaeffer (Co-Chair, Coronado Republican Club (CRC)).
- **Rebuttals**: none printed.

The argument's claims (Proposition R of 1972, the 2023 settlement, SANDAG's job counts) are the author's; no official record I fetched confirms them.

### Full text

S1 PDF p. 77, "FULL TEXT OF MEASURE D". It amends CMC Section 86.56.048 (adding subsection C: "For multiple-family development in the R-4 Multiple-Family Residential Zone, a maximum building height of four stories and not more than 42 feet shall apply.") and OACSP Chapter V, Part B, Section B.2 (new subsection b: multiple family dwellings "shall not contain more than four stories", 40 feet flat roof / 42 feet sloped roof of 2:12 and greater). The text says "bold underline represents new text and strikethrough represents deleted text"; `pdftotext` loses that formatting, so read the PDF page.

### Tax rate statement or fiscal analysis

None printed. Not a tax measure.
