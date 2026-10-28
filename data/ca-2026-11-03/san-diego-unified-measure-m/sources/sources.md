# San Diego Unified School District Measure M: sources

Measure M: "SAN DIEGO UNIFIED SCHOOL DISTRICT REPAIR, STUDENT SAFETY, NO TAX RATE INCREASE MEASURE" (general obligation bond, $3,500,000,000)
Election: November 3, 2026, Gubernatorial General Election
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide, **ballot type 329**, PDF title "November 3 2026 General - San Diego", 132 pages, created 2026-09-23 | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-329.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 (English facsimile reference ballot) | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | San Diego County Registrar of Voters (document of the SDUSD Board of Education) | "Resolution of the Board of Education of the San Diego Unified School District Ordering a School Bond Election...", adopted July 14, 2026, with exhibits; scanned, 142 pages, no text layer; ROV received stamp "2026 JUL 16" | https://www.sdvote.com/content/dam/rov/en/election/nov-3-2026-gubernatorial-general-election/san-diego-unified-school-district.pdf |

How I found ballot type 329: the SanGIS layer *Election_Precinct_2026_11_03* (https://geo.sandag.org/server/rest/services/Hosted/Election_Precinct_2026_11_03/FeatureServer/0, attribute `bt` = ballot type) lists consolidated precinct "CLAIREMONT E" (25,870 registered voters, inside the City of San Diego) on ballot type 329. I used that layer only as a finder; the contents of S1 itself confirm Measure M is on ballot type 329. Saved attributes: `../../raw/sangis-election-precinct-2026-11-03-attrs.json`.

Page numbers: "PDF p." is the page in S1. The printed footer ("SD 329-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig329-p44-sample-ballot-page.pdf` | S1, PDF p. 44 (SD 329-042) | Sample ballot page with Measure M |
| `vig329-p76-ballot-label-impartial-analysis-tax-statement.pdf` | S1, PDF p. 76 (SD 329-074) | Ballot label, vote threshold, County Counsel impartial analysis, Tax Information Statement |
| `vig329-p77-argument-in-favor-no-argument-against.pdf` | S1, PDF p. 77 (SD 329-075) | Argument in favor; notice that no argument against was filed; start of full text |
| `vig329-p77-126-full-text.pdf` | S1, PDF pp. 77-126 (SD 329-075 to 329-124) | Full text of Measure M, including the Bond Project List, ending "[End of Full Text of Proposition]" |
| `composite-ballot-p22.pdf` | S2, PDF p. 22 | Ballot as printed, with letter |
| `rov-board-of-education-resolution-2026-07-14.pdf` | S3, whole file | Board resolution (PDF pp. 1-8) and exhibits (Exhibit A, the full text, begins PDF p. 9) |

Cut commands: `qpdf SB-ENG-329.pdf --pages . <range> -- <out>`.

## Facts and the passages that establish them

### Ballot question (ballot label)

S1 PDF p. 76 ("This measure will appear on the ballot in the following form."), same on S1 p. 44 and S2 p. 22:

> MEASURE M
> SAN DIEGO UNIFIED SCHOOL DISTRICT REPAIR, STUDENT SAFETY, NO TAX RATE INCREASE MEASURE
> To repair/upgrade all public schools, help retain/attract teachers by:
> • Repairing deteriorating roofs, plumbing, restrooms;
> • Providing safe drinking water;
> • Removing asbestos, lead paint, mold;
> • Upgrading outdated career/vocational, science, technology, engineering classrooms;
> shall San Diego Unified School District's measure authorizing $3,500,000,000 in bonds at legal rates, levying $32 per $100,000 of assessed value, providing $204,000,000 annually while bonds are outstanding, requiring public spending disclosure, audits, citizens oversight, be adopted?
> Bonds – Yes / Bonds – No

### Vote required

S1 PDF p. 76:

> This measure requires 55% of those voting on the measure.

### Who votes on it

S3, Section 2 (PDF p. 5):

> a special election shall be held within the boundaries of the District on November 3, 2026, for the purpose of submitting to the registered voters of the District the bond measure contained in Exhibit A

S1 PDF p. 77 (full text, "BOND AUTHORIZATION"):

> By approval of this proposition by at least 55% of the voters of the San Diego Unified School District (the "District") voting on the proposition, the District shall be authorized to issue and sell bonds of $3.5 billion in aggregate principal amount

In short: the registered voters of the San Diego Unified School District.

### Who placed it on the ballot

S1 PDF p. 76 (impartial analysis):

> The Board of Education for the San Diego Unified School District ("District") placed this measure on the ballot.

S3 PDF p. 8: "PASSED AND ADOPTED this day July 14, 2026", AYES 5, NOES 0, ABSTAIN 0, ABSENT 0 (handwritten).

### Impartial analysis

S1 PDF p. 76, headed "COUNTY COUNSEL IMPARTIAL ANALYSIS". Key statements:

> The District estimates the average tax rate would be $32 for every $100,000 of assessed valuation, and the highest tax rate would be approximately $59.18 for every $100,000 of assessed valuation. The tax is anticipated to be collected through fiscal year 2062-63.

> The District states that the tax rate limitation in Proposition S, approved by voters on November 4, 2008, does not apply to the tax rate of the bonds proposed by this measure. The District states that if the bond issuance causes the District to exceed its statutory bonding limit, this measure authorizes the District to seek a waiver of the limit.

> The estimated total debt service, including principal and interest, required to be repaid if the bonds are issued and sold is approximately $8,100,000,000.

> The District shall set aside $567,000,000 of the proceeds for charter school projects, with the amount adjusted based on the proportion of students attending charter schools. Approval of this measure does not guarantee the proposed projects will be funded by the sale of the bonds.

> A "YES" vote is in favor of authorizing the District to issue and sell $3,500,000,000 in general obligation bonds.
> A "NO" vote is against authorizing the District to issue and sell $3,500,000,000 in general obligation bonds.

### Tax rate statement

S1 PDF p. 76, "TAX INFORMATION STATEMENT", dated July 14, 2026, signed "/s/ Dr. Fabi Bagula, Superintendent, San Diego Unified School District":

> 1. The best estimate of the average annual tax rate ... is 3.2 cents per $100 ($32.00 per $100,000) of assessed valuation. The final fiscal year in which the tax to be levied to fund this bond issue is anticipated to be collected is fiscal year 2062-63.
> 2. The best estimate of the highest tax rate ... is 5.918 cents per $100 ($59.18 per $100,000) of assessed valuation in fiscal year 2036-37.
> 3. The best estimate of the total debt service ... is approximately $8,100,000,000.

### Arguments and rebuttals

- **Argument in favor**, S1 PDF p. 77. Title line: "URGENTLY NEEDED REPAIRS FOR NEIGHBORHOOD SCHOOLS WITHOUT RAISING OUR TAXES." Signers: Mark Kersey (President & CEO, San Diego County Taxpayers Association); Phil Blair (Former Chair, San Diego Regional Chamber of Commerce); Todd Jarvis (Chief of Police, San Diego Schools Police Department); Monique Barrett (President, San Diego Education Association); Yen Trieu-Corpus (Paradise Hills Parent).
- **Argument against**: none. S1 PDF p. 77: "No Argument Against Measure M was filed with the Office of the Registrar of Voters".
- **Rebuttals**: none printed in S1.

### Full text

S1 PDF pp. 77-126, headed "FULL TEXT OF MEASURE M". It begins:

> This proposition may be known and referred to as the "San Diego Unified School District Repair, Student Safety, No Tax Rate Increase Measure" or as "Measure M".

It ends (PDF p. 126): "[End of Full Text of Proposition]".

### Other facts in the record, worth checking before use

- S3 recitals (PDF pp. 1-2) list earlier voter-approved SDUSD bonds: Proposition MM (Nov 3, 1998, $1.51 billion), Proposition S (Nov 4, 2008, $2.1 billion), Proposition Z (Nov 6, 2012, $2.8 billion), Measure YY (Nov 6, 2018, $3.5 billion), Measure U (Nov 8, 2022, $3.2 billion).
- S3 recitals (PDF p. 3) say the Bond Project List includes "workforce housing for teachers and staff".
- S3 recital (PDF p. 1): "approximately 16.2% of students residing in the District are expected to attend charter schools during the 2026-27 school year".
