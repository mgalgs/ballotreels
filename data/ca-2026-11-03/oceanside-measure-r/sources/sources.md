# City of Oceanside Measure R: sources

Measure R: Oceanside City Charter amendment (Sections 301, 302 and 303: public works contracts, prevailing wage, project labor agreements)
Election: November 3, 2026, Gubernatorial General Election (consolidated)
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide, **ballot type 160**, PDF title "November 3 2026 General - San Diego", 92 pages, created 2026-09-23 | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-160.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | City of Oceanside, City Clerk | "Current Elections" page, named in the impartial analysis as where the text of Measure R is posted | https://www.ci.oceanside.ca.us/government/city-clerk/elections-fair-political-practices-commission-reporting-program/current-elections |

**S3 is blocked.** A plain GET returned HTTP 403 "Access Denied" (Akamai edge, reference #18.caa6dc17.1793224217.7de10269), saved as `../../raw/oceanside-clerk-current-elections-HTTP403.html`. I did not try to get around it. The City Clerk's own documents (the council resolution placing Measure R on the ballot, and any posted text) are therefore **not archived**; see "Needs manual download" in the county README.

Ballot type 160 is an Oceanside precinct (found via the SanGIS *Election_Precinct_2026_11_03* layer, attribute `bt`; finder only). S1 itself confirms Measures R and S are on it.

Page numbers: "PDF p." is the page in S1. The printed footer ("SD 160-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig160-p44-sample-ballot-page.pdf` | S1, PDF p. 44 | Sample ballot page with Measures R and S |
| `vig160-p76-ballot-label-impartial-analysis.pdf` | S1, PDF p. 76 (SD 160-074) | Ballot label, vote threshold, City Attorney impartial analysis |
| `vig160-p77-78-arguments-and-rebuttals.pdf` | S1, PDF pp. 77-78 (SD 160-075 to 160-076) | Argument in favor and rebuttal to it (p. 77); argument against and rebuttal to it (p. 78) |
| `vig160-p79-full-text.pdf` | S1, PDF p. 79 (SD 160-077) | "FULL TEXT OF MEASURE R, Exhibit A": amended Charter Sections 301-303 |
| `composite-ballot-p21.pdf` | S2, PDF p. 21 | Ballot as printed, with letter |

## Facts and the passages that establish them

### Ballot question

S1 PDF p. 76 ("This measure will appear on the ballot in the following form."):

> MEASURE R
> To preserve the City's ability to continue receiving state infrastructure funding for public works projects, shall the Oceanside City Charter be amended to conform to state laws and best practices regarding prevailing wage and fair competition, including the use of project labor agreements for City public works with mandatory provisions for taxpayer protections, transparency, and accountability in the contracting process, by amending Sections 301, 302, and 303 of the Oceanside City Charter?

### Vote required

S1 PDF p. 76: "This measure requires Simple Majority (50%+1) of those voting on the measure."

### Who votes on it

The guide prints Measure R under the heading "CITY OF OCEANSIDE" (S1 PDF pp. 44, 76) and the impartial analysis says "If approved by voters, Measure R would amend Sections 301, 302 and 303 of the Charter of the City of Oceanside". **No document I could fetch states the electorate in words** (for example "the qualified voters of the City of Oceanside"); the council resolution that would say so is on the blocked City Clerk site. Unconfirmed beyond "voters of the City of Oceanside" as implied by the heading.

### Who placed it on the ballot

S1 PDF p. 76: "Measure "R" was placed on the ballot by the Oceanside City Council." The resolution number and date are not in S1.

### Impartial analysis

S1 PDF p. 76, "CITY ATTORNEY IMPARTIAL ANALYSIS", "Dated: August 14, 2026", "Steven Burke, Jr., City Attorney". Key statements:

> Specifically, Measure R would affirm prevailing wage requirements for all public works projects as defined in paragraph (1) of subdivision (d) of Section 1782 of the California Labor Code and, consistent with Public Contract Code sections 2500-2503, would affirmatively allow, but not require, the City Council to enter into or require a project labor agreement ("PLA") for City public works projects that includes the taxpayer protection provisions of Public Contract Code section 2500.

> The Charter was approved by Oceanside voters in 2010. As adopted, the Charter generally exempts the City from state laws regulating public works contracting except as provided by ordinance or by agreement approved by the City Council

> The City has maintained its qualified status for state public works funding based on interpretations that state law and the Charter can be reconciled. The City Attorney confirmed the City's ongoing eligibility for state funding with the Department of Industrial Relations in 2014. The City pays prevailing wage on public works projects consistent with state law under the existing Charter.

> If adopted, Measure R's amendment of Sections 301, 302 and 303 would ensure the City's continuing eligibility for state funding for infrastructure projects.

> A "yes" vote on Measure R favors amending the Oceanside City Charter.
> A "no" vote on Measure R opposes amending the Oceanside City Charter.

(The signature line reads "Steven Burke, Jr." here and "T. Steven Burke, Jr." under Measure S, as printed.)

### Arguments and rebuttals

All four are printed.

- **Argument in favor**, S1 PDF p. 77. Headline: "Vote YES on R / City Charter Clean Up Amendments To Protect Oceanside's State Funding". Signers: Lorenzo Miles (Training Director, Sheet Metal Apprenticeship); Sean-Keoni Ellis (USMC Veteran Former Lead Instructor, Veterans In Piping - Camp Pendleton); Terence Webster (USMC ret. Police and Fire Commissioner, City of Oceanside); Esther Sanchez (Mayor, City of Oceanside); Linda Legerrette (Board Member, Middle Class Taxpayers Association).
- **Rebuttal to the argument in favor**, S1 PDF p. 77. Headline: "Vote NO on R". Signers: Sandra Levee (Concerned Citizen); Colette Kelley (Accountant); Adrianne Silveria (Concerned Citizen); James Silveria (Teamsters Commercial Truck Driver); Rafael Martinez (no title printed).
- **Argument against**, S1 PDF p. 78. First line: "The City of Oceanside claims that Measure R will ensure Oceanside is in compliance with state requirements for funding but the city is already in complete compliance and continues to qualify for State funding." Signers: Sandra Levee, Colette Kelley, Adrianne Silveria, James Silveria, Rafael Martinez (no titles printed).
- **Rebuttal to the argument against**, S1 PDF p. 78. Headline: "The Opponents Have The Facts WRONG…". Signers: the same five as the argument in favor.

### Full text

S1 PDF p. 79, "FULL TEXT OF MEASURE R / Exhibit A":

> Note: Proposed additions to the Charter are underlined text. Deletions are in strikethrough text. Unchanged text is neither underlined or in strikethrough.

**Caution:** `pdftotext` drops the underline and strikethrough, so text extracted from this page mixes old and new wording. Read the PDF page itself to tell additions from deletions.

### Tax rate statement or fiscal analysis

None printed. Not a tax measure.
