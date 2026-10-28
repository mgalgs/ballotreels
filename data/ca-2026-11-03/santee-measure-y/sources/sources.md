# City of Santee Measure Y: sources

Measure Y: one percent (1%) general transactions and use (sales) tax for ten years
Election: November 3, 2026, General Municipal Election (consolidated with the Gubernatorial General Election)
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide, **ballot type 365**, PDF title "November 3 2026 General - San Diego", 92 pages | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-365.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | City of Santee, City Clerk | Resolution No. 071-2026, "A Resolution of the City Council of the City of Santee, California Calling for the Placement of a General Tax Measure on the Ballot ... for the Submission to the Qualified Voters of an Ordinance to Enact a General Transactions and Use Tax (Sales Tax) at the Rate of One Percent (1%) for Ten (10) Years", adopted June 24, 2026, with Exhibit "A" (the ordinance); 16 pages, scanned, no text layer | https://www.cityofsanteeca.gov/documents/city-clerk/elections/2026%20Resolutions/reso-071-2026.pdf |
| S4 | City of Santee, City Clerk | "City Attorney Impartial Analysis of Measure Y" | https://www.cityofsanteeca.gov/documents/city-clerk/elections/2026-measure-documents/impartial-analysis.pdf |
| S5 | City of Santee, City Clerk | June 24, 2026, Council Agenda Item 18 (5 pages) | https://www.cityofsanteeca.gov/documents/city-clerk/elections/2026-measure-documents/06-24-2026-item-18.pdf |
| S6 | City of Santee, City Clerk | "Elections and How to Vote" page, which lists the documents above | https://www.cityofsanteeca.gov/departments/city-clerk/elections-and-how-to-vote |

Ballot type 365 is a Santee precinct (SanGIS *Election_Precinct_2026_11_03* layer, attribute `bt`; finder only). S1 confirms Measure Y is on it, together with Measures G and BB.

The City Clerk page (S6) also posts, and I did **not** download: Resolutions 072-2026 (consolidation request) and 073-2026 (rules for arguments); the February 25, 2026 Item 9 and June 12, 2026 Item 8 agenda items; and separate PDFs of each argument and rebuttal. The guide prints all four arguments, so those PDFs would be duplicates.

Page numbers: "PDF p." is the page in S1. The printed footer ("SD 365-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig365-p44-sample-ballot-page.pdf` | S1, PDF p. 44 | Sample ballot page with Measures Y, G and BB |
| `vig365-p79-ballot-label-impartial-analysis.pdf` | S1, PDF p. 79 (SD 365-077) | Ballot label, vote threshold, City Attorney impartial analysis |
| `vig365-p80-81-arguments-and-rebuttals.pdf` | S1, PDF pp. 80-81 (SD 365-078 to 365-079) | Argument in favor and rebuttal (p. 80); argument against and rebuttal (p. 81) |
| `composite-ballot-p21.pdf` | S2, PDF p. 21 | Ballot as printed, with letter |
| `santee-clerk-resolution-071-2026-calling-election-general-tax-measure.pdf` | S3, whole file | Resolution (PDF pp. 1-5) and Exhibit "A", the Transactions and Use Tax Ordinance (PDF pp. 6-16) |
| `santee-clerk-impartial-analysis.pdf` | S4, whole file | City Attorney's analysis as posted by the City |
| `santee-clerk-council-agenda-2026-06-24-item-18.pdf` | S5, whole file | Council agenda item for the June 24, 2026 vote |
| `santee-clerk-elections-and-how-to-vote.html` | S6 | The listing page |

## Facts and the passages that establish them

### Ballot question

S1 PDF p. 79 (and S3, Section 3, PDF p. 2, identical wording):

> MEASURE Y
> "To provide funding for City of Santee services and infrastructure, such as fixing streets and potholes; keeping streets, sidewalks, parks and public facilities safe, clean, and well-maintained; repairing / replacing aging infrastructure and stormdrains; local traffic management; fire protection, paramedic, crime prevention, and 911 emergency response, shall City of Santee's measure establishing a one cent sales tax be adopted, providing approximately $14,000,000 annually for city services for 10 years, with independent audits, citizens' committee oversight, and all funds locally controlled?"

### Vote required

S1 PDF p. 79: "This measure requires Simple Majority (50%+1) of those voting on the measure."

### Who votes on it

S3, Section 2 (PDF p. 2):

> the City Council, by a two-thirds (2/3) vote of all members, hereby orders the Measure to be submitted to the voters of the City at the General Municipal Election to be held on Tuesday, November 3, 2026.

S3 title: "for the Submission to the Qualified Voters of an Ordinance ...". Section 3: "On the ballot to be submitted to the qualified voters at the General Municipal Election".

In short: the qualified voters of the City of Santee.

### Who placed it on the ballot

S1 PDF p. 79: "On June 24, 2026, the City Council voted to place Measure "Y" on the November 3, 2026 General Municipal Election ballot."

S3 PDF p. 4: "ADOPTED by the City Council of the City of Santee, California, at a Regular Meeting thereof held this 24th day of June 2026, by the following roll call vote to wit: AYES: KOVAL, MCNELIS, MINTO, TROTTER; NOES: HALL; ABSENT: NONE". Signed John W. Minto, Mayor; attested James Jeffries, City Clerk.

### Impartial analysis

S1 PDF p. 79, "CITY ATTORNEY IMPARTIAL ANALYSIS / 1% GENERAL TRANSACTIONS AND USE (SALES) TAX FOR TEN (10) YEARS", signed "/s/ SHAWN HAGERTY, City Attorney". Key statements:

> If approved by a majority of Santee voters, this Measure would authorize a one percent (1%) retail transactions and use (sales) tax within the City of Santee. It is estimated that Measure "Y" will provide an additional $14,000,000 in annual local funding for ten (10) years

> This tax would be a "general tax," meaning that revenues raised from the tax would go into the City's general fund to pay for any lawful City program, improvement, or service.

> If approved, the tax would become operative on April 1, 2027 and remain in effect for ten (10) years until it expires on March 31, 2037.

> Measure "Y" establishes a five (5) member Citizens' Oversight Committee consisting of Santee residents, property owners and business owners appointed by the City Council.

> A "yes" vote on Measure "Y" will authorize the 1% transactions and use (sales) tax for 10 years.
> A "no" vote on Measure "Y" will not authorize the 1% transactions and use (sales) tax for 10 years.

### Arguments and rebuttals

All four are printed.

- **Argument in favor**, S1 PDF p. 80. First line: "Some will say the City should live within its means. It does." Signers: John Minto (Mayor of Santee); Barbara Ryan (Santee School Board Member (1980-2028)); John Hossick (Santee Mobile Home Owners Action Committee); Adam Daniels (President, Santee Fire Fighters Association); Mark Kersey (Executive Director, San Diego County Taxpayers Association).
- **Rebuttal to the argument in favor**, S1 PDF p. 80. First line: "Don't be fooled, Santee friends and neighbors!" Signers: Tony Shephard (Resident / Businessman); Allie Senterfitt (Teacher); James Wilson (Retired Army / Resident); Shela Tong (Resident); Michael Usrey (Retired / Resident).
- **Argument against**, S1 PDF p. 81. Headline: "Protect Santee Families - Vote "NO" on Raising Taxes!" Signers: Tony Shephard (Santee resident); James Wilson (Retired US Army); Sheila Tong; Allie Senterfitt (Teacher); Michael Usrey (Retired).
- **Rebuttal to the argument against**, S1 PDF p. 81. First line: "Measure Y has been vetted and endorsed by longtime residents and elected leaders". Signers: John Minto (Mayor of Santee); Jim Bartell (Charter Santee City Councilman (1980-2002)); Barbara Ryan (Santee School Board Member (1980-2028)); John Hossick (Santee Mobile Home Owners Action Committee); Adam Daniels (President, Santee Fire Fighters Association).

Recorded as printed: the same signer is "SHELA TONG" in the rebuttal and "SHEILA TONG" in the argument against. Mark Kersey's title here is "Executive Director"; in the other measures' arguments it is "President & CEO". Barbara Ryan's dates read "(1980-2028)".

### Full text

**The guide does not print the full text of Measure Y.** S3, Section 7 (PDF p. 3):

> The full text of the Measure shall not be printed in the voter information guide, and a statement shall be printed on the ballot pursuant to Elections Code section 9223 advising voters that they may obtain a copy of this Resolution and the Measure, at no cost, upon request made to the City Clerk.

The full text is Exhibit "A", "Transactions and Use Tax Ordinance", S3 PDF pp. 6-16 (archived here). S3 recitals say it adds "Chapter 3.36 to Title 3 of the City's Municipal Code".

### Tax rate statement or fiscal analysis

None printed (not a bond). The fiscal facts are the City Attorney's: 1%, about $14,000,000 a year, April 1, 2027 to March 31, 2037.
