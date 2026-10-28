# Grossmont-Cuyamaca Community College District Measure G: sources

Measure G: "Grossmont-Cuyamaca Community College District Fire Safety, Job Training, College Affordability, No Tax Rate Increase" (general obligation bond, $624,000,000)
Election: November 3, 2026, Gubernatorial General Election
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide, **ballot type 365**, PDF title "November 3 2026 General - San Diego", 92 pages, created 2026-09-23 | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-365.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | San Diego County Registrar of Voters (document of the District) | Governing Board Resolution No. 26-007, "Ordering an Election to Authorize the Issuance of General Obligation Bonds...", adopted July 27, 2026, with Appendix A (full text) and Appendix B (ballot label); 17 pages, scanned with OCR text layer | https://www.sdvote.com/content/dam/rov/en/election/nov-3-2026-gubernatorial-general-election/grossmont-cuyamaca-ccd.pdf |

Ballot type 365 is a Santee precinct (found via the SanGIS *Election_Precinct_2026_11_03* layer, attribute `bt`; finder only). S1's contents confirm Measure G is on it. Measure G also appears in the guides for ballot types 001, 002, 575, 581 and 653, which I fetched for other measures; I compared only the presence of the measure, not the pages.

Page numbers: "PDF p." is the page in S1. The printed footer ("SD 365-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig365-p44-sample-ballot-page.pdf` | S1, PDF p. 44 | Sample ballot page with Measure G |
| `vig365-p82-ballot-label-impartial-analysis-tax-rate-statement.pdf` | S1, PDF p. 82 (SD 365-080) | Ballot label, vote threshold, County Counsel impartial analysis, Tax Rate Statement |
| `vig365-p83-argument-in-favor-no-argument-against.pdf` | S1, PDF p. 83 (SD 365-081) | Argument in favor; notice that no argument against was filed; start of full text |
| `vig365-p83-85-full-text.pdf` | S1, PDF pp. 83-85 (SD 365-081 to 365-083) | Full text of Measure G, ending "full text of measure ends at the above line." |
| `composite-ballot-p21.pdf` | S2, PDF p. 21 | Ballot as printed |
| `rov-governing-board-resolution-26-007.pdf` | S3, whole file | The District's resolution ordering the election, with appendices |

## Facts and the passages that establish them

### Ballot question (ballot label)

S1 PDF p. 82 ("This measure will appear on the ballot in the following form."):

> MEASURE G
> Grossmont-Cuyamaca Community College District Fire Safety, Job Training, College Affordability, No Tax Rate Increase
> With funds that cannot be taken by the State and spent elsewhere and NO tax rate increase, shall Grossmont-Cuyamaca Community College District's measure to
> • improve/expand career training classrooms
> • remove asbestos/mold
> • reduce wildfire threats
> • maintain college affordability
> be adopted, authorizing $624 million of bonds with legal rates, levies below $25/$100,000 assessed valuation while outstanding ($45 million annually), audits, taxpayer oversight, full disclosure of all spending?
> Bonds – Yes / Bonds – No

### Vote required

S1 PDF p. 82: "This measure requires 55% of those voting on the measure."

### Who votes on it

S3, Section 2 (PDF p. 5 of the resolution, OCR text):

> The Board hereby orders an election and submits to the electors of the District the question of whether general obligation bonds of the District shall be issued and sold in a maximum principal amount of $624,000,000

S1 PDF p. 83 (full text, "BOND AUTHORIZATION"):

> By approval of this measure by at least 55% of the registered voters voting on the measure, the Grossmont-Cuyamaca Community College District (the "District") will be authorized to issue and sell bonds of up to $624,000,000

In short: the electors (registered voters) of the Grossmont-Cuyamaca Community College District.

### Who placed it on the ballot

S1 PDF p. 82 (impartial analysis): "The Governing Board for the Grossmont-Cuyamaca Community College District ("District") placed this measure on the ballot."

S3 (signature page): "The foregoing Resolution was adopted by the Governing Board of the Grossmont-Cuyamaca Community College District of San Diego County ... by the following vote, on July 27, 2026." AYES (as OCR'd): "Adams, Justeson, Monroe, Page, Schorr, Cruz (Advisory), Garcia (Advisory)"; NOES, ABSENT, ABSTAIN blank.

### Impartial analysis

S1 PDF p. 82, "COUNTY COUNSEL IMPARTIAL ANALYSIS". Key statements:

> If approved by 55% of the votes cast, this measure will authorize the District to issue and sell general obligation bonds in an amount not to exceed $624,000,000.

> The District estimates the average tax rate would be $24.67 for every $100,000 of assessed valuation, and the highest tax rate would be approximately $24.98 for every $100,000 of assessed valuation. The tax is anticipated to be collected through fiscal year 2058-2059.

> The estimated total debt service, including principal and interest, required to be repaid if the bonds are issued and sold is approximately $1,246,250,216.

> Approval of this measure does not guarantee the proposed projects will be funded by the sale of the bonds.

### Tax rate statement

S1 PDF p. 82, "TAX RATE STATEMENT", signed "/s/ Lynn Ceresino Neault, Ed.D., Chancellor":

> 1. The best estimate of the average annual tax rate ... is $24.67 per $100,000 of assessed valuation. It is currently expected that the tax will be collected until fiscal year 2058-59.
> 2. The best estimate of the highest tax rate ... is $24.98 per $100,000 of assessed valuation. This rate is projected to apply beginning in fiscal year 2031-32.
> 3. The best estimate of total debt service ... will be approximately $1,246,250,216.

and

> The tax rate for previous general obligations totaled $37.52 per $100,000 of assessed value for fiscal year 2025-26. The District does not currently expect the fiscal year 2025-26 tax rate to be increased as a result of the issuance of bonds pursuant to this bond measure.

### Arguments and rebuttals

- **Argument in favor**, S1 PDF p. 83. Title line: "URGENTLY NEEDED REPAIRS WITHOUT RAISING TAXES". It says: "Measure G extends the tax rate authorized by voters in 2002". Signers: Mark Kersey (President & CEO, San Diego County Taxpayers Association); Cody Martinez (Tribal Chairman, Sycuan Band of the Kumeyaay Nation); Mark Arapostathis (Mayor, City of La Mesa); Jim Mahler (President, American Federation of Teachers Grossmont-Cuyamaca Community College District); Margaret Osborne, R.N. (Member, California Nurses Association).
- **Argument against**: none. S1 PDF p. 83: "No Argument Against Measure G was filed with the Office of the Registrar of Voters".
- **Rebuttals**: none printed.

### Full text

S1 PDF pp. 83-85, "FULL TEXT OF MEASURE G". It opens: "The full text of bond measure to be printed in the election material begins below the following line." and closes on p. 85 with "full text of measure ends at the above line."
