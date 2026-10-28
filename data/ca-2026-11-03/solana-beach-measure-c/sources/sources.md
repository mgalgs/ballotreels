# City of Solana Beach Measure C: sources

Measure C: update the transient occupancy (hotel) tax and raise the rate from 13% to 14% (Proposed Ordinance 545, a general tax)
Election: November 3, 2026, General Municipal Election (consolidated with the Statewide General Election)
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide, **ballot type 236**, PDF title "November 3 2026 General - San Diego" | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-236.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | City of Solana Beach, City Clerk | Resolution 2026-100, "Calling and Giving Notice of the Holding of a General Municipal Election ... for the Submission to the Voters a Question Relating to a Measure Updating the City's Transient Occupancy (Hotel) Tax and Increasing the Transient Occupancy Tax Rate from 13% to 14%...", adopted July 15, 2026 (7 pages, no text layer) | https://www.cityofsolanabeach.ca.gov/sites/default/files/Solana%20Beach/City%20Clerk/Election%20Information/Measure/res-2026-100-07-15-26-tot-measure.pdf |
| S4 | City of Solana Beach, City Clerk | "Proposed Ordinance 545" | https://www.cityofsolanabeach.ca.gov/sites/default/files/Solana%20Beach/City%20Clerk/Election%20Information/Resolutions/ballot%20measure/proposed-ord-545-tot.pdf |
| S5 | City of Solana Beach, City Clerk | Impartial Analysis (file dated 8-13-26) | https://www.cityofsolanabeach.ca.gov/sites/default/files/Solana%20Beach/City%20Clerk/Election%20Information/Measure/solana-beach-tot-impartial-analysis-8-13-26.pdf |
| S6 | City of Solana Beach, City Clerk | "Election Info" page listing the above | https://www.cityofsolanabeach.ca.gov/en/election-info |

Ballot type 236 is a Solana Beach precinct (SanGIS *Election_Precinct_2026_11_03* layer, attribute `bt`; finder only). S1 confirms Measure C is on it.

S6 also links an "Argument in Favor of Measure C" PDF (8-3-26), Resolutions 2026-036/037/038 (calling the election, consolidation, candidate statements) and a "Measure C webpage" (`/en/MeasureC`), which I did not download. The guide prints the argument.

Page numbers: "PDF p." is the page in S1. The printed footer ("SD 236-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig236-p44-sample-ballot-page.pdf` | S1, PDF p. 44 | Sample ballot page with Measure C |
| `vig236-p77-ballot-label-impartial-analysis-argument-in-favor.pdf` | S1, PDF p. 77 (SD 236-075) | Ballot label, vote threshold, City Attorney impartial analysis, argument in favor |
| `vig236-p78-79-full-text-ordinance-545.pdf` | S1, PDF pp. 78-79 (SD 236-076 to 236-077) | Full text: Proposed Ordinance 545 |
| `composite-ballot-p21.pdf` | S2, PDF p. 21 | Ballot as printed, with letter |
| `solana-beach-clerk-*.pdf`, `.html` | S3-S6 | City Clerk documents |

## Facts and the passages that establish them

### Ballot question

S1 PDF p. 77 (same wording in S3 Section 4, p. 3):

> MEASURE C
> To provide general city services such as keeping beaches, parks, trails, and restrooms safe, clean and well-maintained; preventing trash from entering local beaches/lagoons; upgrading emergency response/safety facilities, shall City of Solana Beach's measure updating the 20-year-old transient occupancy tax (paid only by hotel/short-term vacation rental guests as specified in ordinance) and increasing the rate by 1% be adopted, providing approximately $250,000 annually until ended by voters, with all money locally controlled?

### Vote required

S1 PDF p. 77: "This measure requires Simple Majority (50%+1) of those voting on the measure."

### Who votes on it

S3, Section 3 (p. 3):

> there is called and ordered to be held in the City of Solana Beach, California, on Tuesday, November 3, 2026, a General Municipal Election for the purpose submitting to the voters of the City of Solana Beach a question relating to a ballot measure that, if approved by a majority of the voters (50% +1), amends Chapter 3.36 of Title 3 of the Solana Beach Municipal Code

(The words "for the purpose submitting" are as printed.) S1 PDF p. 79 (ordinance Section 12): "approved the Ordinance by a vote of no less than a majority of the votes cast by the electors voting at the General Municipal Election held on Tuesday, November 3, 2026".

In short: the voters of the City of Solana Beach.

### Who placed it on the ballot

S1 PDF p. 77: "The Solana Beach City Council placed Measure C on the ballot."

S3 p. 7: "PASSED, ADOPTED, AND APPROVED by the City Council of the City of Solana Beach, California, at a regular meeting thereof this 15th day of July, 2026 by the following vote to wit: AYES: Councilmembers – Heebner, Zito, Edson, Becker; NOES: Councilmembers – None; ABSTAIN: Councilmembers – None; ABSENT: Councilmembers – MacDonald". Signed Lesa Heebner, Mayor; attested Angela Ivey, City Clerk.

### Impartial analysis

S1 PDF p. 77, "CITY ATTORNEY'S IMPARTIAL ANALYSIS", signed "JOHANNA N. CANLAS, City Attorney, City of Solana Beach". Key statements:

> Currently, the City charges a 13% TOT. If approved, this Measure would increase the TOT rate by 1% for a total of 14% and would generate an estimated $250,000 per year in additional revenue. The Measure's 1% increase is a "general tax." Thus, revenue generated by the Measure is unrestricted and may be used for any general governmental purpose of the City.

> This Measure defines "Rent" to include cleaning fees, resort fees, parking fees, pet fees, extra guest fees, cancellation charges, WIFI/Internet charges, and any other fees, rates and charges as part of the total "rent" charged, but excludes fees, rates and charges not collected directly.

> if a web- or application-based hosting platform, online travel company, or third-party booking vendor that facilitates rentals and payments for rentals is used, the hosting platform, online travel company, or third-party booking vendor is considered an agent of the operator for the purposes of collecting and remitting the TOT to the City.

> A "yes" vote favors the Measure. A "no" vote opposes the Measure. This Measure requires a simple majority of votes in favor to pass (50% + 1).

### Arguments and rebuttals

- **Argument in favor**, S1 PDF p. 77. First line: "It seems every list of "Top Ten Best Places to Live" and "Beach Towns Not to Miss" includes Solana Beach." Signers: Amy Bryan (Doctor of Audiology, 20 year resident Co-founder Solana Beach Free Farmers Market); Tom Golich (Former Solana Beach Mayor 60 year resident); Gregory Petre (Co-Chair Solana Beach Chamber of Commerce Board of Directors 47 year resident); John Steel (President, Condominium Organizations of South Sierra Avenue 20 year resident); Rich Villasenor (Owner Solana Frosty Fourth generation Solana Beach resident).
- **Argument against**: **none printed.** S1 has no argument against Measure C and no printed "no argument was filed" notice (I searched the full text of S1).
- **Rebuttals**: none printed.

Recorded as found: the argument in favor says "Join our unanimous Solana Beach City Council"; S3 records four ayes with Councilmember MacDonald absent.

### Full text

S1 PDF pp. 78-79, "FULL TEXT OF MEASURE C / PROPOSED ORDINANCE 545", "AN ORDINANCE OF THE CITY OF SOLANA BEACH, CALIFORNIA, AMENDING CHAPTER 3.36 OF TITLE 3 OF THE SOLANA BEACH MUNICIPAL CODE TO UPDATE THE CITY'S TRANSIENT OCCUPANCY (HOTEL) TAX AND TO INCREASE THE TRANSIENT OCCUPANCY TAX RATE FROM 13% TO 14%". Key provision, new SBMC 3.36.010.5:

> Beginning on January 1, 2027, for the privilege of occupancy in any hotel, each transient is subject to and shall pay a tax in the amount of one percent of the rent charged by the operator. The tax imposed by this section shall be in addition to the tax imposed by SBMC 3.36.010.

Recorded as printed: the ordinance's Section 3 heading reads "New Section 3.36.015.5" but the text adds "Section 3.36.030.5".

### Tax rate statement or fiscal analysis

No separate statement (not a bond). The fiscal facts are the City Attorney's: 13% to 14%, about $250,000 a year.
