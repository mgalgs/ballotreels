# County of San Diego Measure A: sources

Measure A: "A TRANSPARENT, ACCOUNTABLE, MODERN COUNTY GOVERNMENT" (San Diego County Charter amendment)
Election: November 3, 2026, Gubernatorial General Election
All files retrieved 2026-10-28 with plain GETs.

## Source documents

| # | Publisher | Title | URL |
|---|-----------|-------|-----|
| S1 | San Diego County Registrar of Voters | Voter Information Guide (sample ballot pamphlet), ballot type 001, PDF title "November 3 2026 General - San Diego", 92 pages, created 2026-09-23 | https://www.sdvote.com/content/dam/rov/en/sb/SB-ENG-001.pdf |
| S2 | San Diego County Registrar of Voters | Composite Ballot - General 2026 (English facsimile reference ballot), 23 pages | https://www.sdvote.com/content/dam/rov/en/election/facsimile-reference-ballot/english-reference-ballot.pdf |
| S3 | San Diego County Registrar of Voters (documents of the Board of Supervisors) | Resolution No. 26-051 (May 19, 2026) and Ordinance No. 11013 (N.S.) (June 25, 2026), scanned, 27 pages | https://www.sdvote.com/content/dam/rov/en/election/nov-3-2026-gubernatorial-general-election/san-diego-county-measure-a-transpansparent-accountable-modern-county-government.pdf |
| S4 | San Diego County Registrar of Voters | Notice of Election and Argument Deadline (dated August 8, 2026) | https://www.sdvote.com/content/dam/rov/en/election/nov-3-2026-gubernatorial-general-election/argument-deadline-measures.pdf |

How I found S1: the sdvote.com sample ballot lookup page builds its PDF link as `/content/dam/rov/en/sb/SB-<language>-<ballot type>.pdf` (code in `/etc.clientlibs/sdc/components/content/rov/election-info-lookup/clientlibs.js`). The lookup itself is a POST, so I did not use it. I fetched ballot type `001` directly. Measures A and B are county-wide, so their pages should be the same in every ballot type, but I checked only type 001.

Page numbers: "PDF p." is the page in S1. The printed footer number ("SD 001-0nn") is 2 lower.

## Files in this directory

| File | Cut from | Contents |
|------|----------|----------|
| `vig-p43-sample-ballot-page.pdf` | S1, PDF p. 43 (printed SD 001-041) | Sample ballot page where Measure A appears |
| `vig-p52-ballot-label-and-impartial-analysis.pdf` | S1, PDF p. 52 (printed SD 001-050) | Ballot label, vote threshold, County Counsel impartial analysis |
| `vig-p53-54-arguments-and-rebuttals.pdf` | S1, PDF pp. 53-54 (printed SD 001-051 to 001-052) | Argument in favor, rebuttal to it; argument against, rebuttal to it |
| `vig-p55-66-full-text.pdf` | S1, PDF pp. 55-66 (printed SD 001-053 to 001-064) | Full text of Measure A (Resolution 26-051 as printed) |
| `composite-ballot-p20.pdf` | S2, PDF p. 20 | Ballot as printed, with letter "MEASURE A" |
| `rov-resolution-26-051-and-ordinance-11013.pdf` | S3, whole file | Resolution 26-051 (PDF pp. 1-24) and Ordinance 11013 (PDF pp. 25-27) |
| `rov-notice-of-election-and-argument-deadline.pdf` | S4, whole file | ROV notice listing the measure text and the argument deadline |

Cut commands: `qpdf SB-ENG-001.pdf --pages . <range> -- <out>` and `qpdf english-reference-ballot.pdf --pages . 20 -- composite-ballot-p20.pdf`.

## Facts and the passages that establish them

### Ballot question (ballot label)

S1 PDF p. 52 and S2 PDF p. 20:

> MEASURE A
> A TRANSPARENT, ACCOUNTABLE, MODERN COUNTY GOVERNMENT
> Shall the San Diego County Charter be amended to establish an Independent Ethics Commission, Independent Budget Analyst, Independent Program Auditor, confirmation of certain senior County leaders, and optional Board of Supervisors appointment of the Public Defender; increase term limits from two to three terms for the Board of Supervisors members; require public disclosure of spending and performance data; clarify non-interference provisions; and update terminology and structure?

The same question (without letter or title) appears in Ordinance 11013, Section 1 (S3) and in S4.

### Vote required

S1 PDF p. 52:

> This measure requires Simple Majority (50%+1) of those voting on the measure.

### Who placed it on the ballot

S1 PDF p. 52 (impartial analysis):

> The Board of Supervisors ("Board") for the County of San Diego ("County") placed this measure on the ballot. If approved by a majority of the votes cast, this measure will amend the County Charter ("Charter") as specified in full text of the ballot measure.

S3, Ordinance 11013, PDF p. 27: adopted June 25, 2026.

> AYES: Aguirre, Lawson-Remer, Montgomery Steppe
> NOES: Anderson, Desmond

### Who votes on it (county-wide)

S3, Ordinance 11013, Section 1 (PDF p. 25):

> a special election is hereby called to be consolidated with the statewide general election to be held on Tuesday, November 3, 2026, for the purpose of submitting to the eligible registered voters of the County of San Diego the following proposition amending the Charter of the County of San Diego:

S2 prints it under the heading "COUNTY".

### Full text

S1 PDF pp. 55-66, headed "FULL TEXT OF MEASURE A". It begins:

> RESOLUTION OF THE BOARD OF SUPERVISORS AMENDING RESOLUTION NO. 26-024 PROPOSING AMENDMENTS TO THE CHARTER OF THE COUNTY OF SAN DIEGO ENTITLED, "A TRANSPARENT, ACCOUNTABLE, MODERN COUNTY GOVERNMENT"

S3, Resolution 26-051, PDF p. 1:

> IT IS RESOLVED AND ORDERED by the Board of Supervisors of the County of San Diego that Resolution No. 26-024, adopted on April 21, 2026, be amended to read in its entirety as follows:

S3, PDF p. 24: Resolution 26-051 was adopted "on this 19th day of May 2026", with AYES Aguirre, Lawson-Remer, Montgomery Steppe and NOES Anderson, Desmond.

Discrepancy, recorded as found: Ordinance 11013 (S3, PDF p. 25) says "The complete text of the proposed amendments ... is set forth in a Resolution adopted by the Board of Supervisors on April 21, 2026". That is the date of Resolution 26-024. The text printed in the guide is Resolution 26-051 (May 19, 2026), which restates 26-024 "in its entirety". The official record does not explain this further.

Text layer caution: S3 is a scan. Its only text layer is OCR of the ordinance, so `pdftotext` of S3 does not give the resolution text. Use S1 PDF pp. 55-66 (born-digital text) for the full text.

### Impartial analysis

S1 PDF p. 52, headed "COUNTY COUNSEL IMPARTIAL ANALYSIS / BALLOT MEASURE TO AMEND COUNTY OF SAN DIEGO CHARTER". On term limits, for example:

> Increase County Supervisors' term limits from two terms to three terms. This amendment would allow a person to serve in the role of County Supervisor for a maximum of twelve years, as opposed to the current maximum of eight years. Any current or former Supervisor's prior time in office would count towards this three-term limit.

It ends:

> A "yes" vote is a vote in favor of the proposed Charter amendments.
> A "no" vote is a vote against amending the Charter.

### Arguments and rebuttals

All four are printed. Each page is headed "ARGUMENTS IN SUPPORT OF OR IN OPPOSITION TO THE PROPOSED LAWS ARE THE OPINIONS OF THE AUTHORS".

- **Argument in favor**, S1 PDF p. 53. Signers: Jim Ross (Firefighter, CALFIRE Firefighters Local #2881); Pat Zaharopoulos (Director/Board, Middle Class Taxpayers Association); Mike O'Deane (President, San Diego Deputy Sheriffs Association); Brigette Browning (President, San Diego & Imperial Counties Labor Council, AFL-CIO); Caridad Sanchez (City Ethics Commissioner, City of San Diego). First line: "Independent Ethics Reform."
- **Rebuttal to the argument in favor**, S1 PDF p. 53. Signers: Jim Desmond (San Diego County Supervisor/Navy Veteran); Carl DeMaio (Chairman, Reform California); Steven Esparza (Chairman, Progressive California Voter Guide); Johnathan Hale (Executive Director, The Transparency Foundation). First line: "Don't fall for deceptive window dressing on Measure A."
- **Argument against**, S1 PDF p. 54. Signers: Jim Desmond, Carl DeMaio, Steven Esparza, Johnathan Hale. First line: "MEASURE A - REPEALS TERM LIMITS".
- **Rebuttal to the argument against**, S1 PDF p. 54. Signers: Jim Ross; Pat Zaharopoulos; Gabriel Markoff (Former Assistant District Attorney); Brigette Browning (President, San Diego Labor Council, AFL-CIO); Caridad Sanchez. First line: "Don't be fooled!"

Note: the rebuttal to the argument against lists Brigette Browning's title as "President, San Diego Labor Council, AFL-CIO". The argument in favor gives it as "President, San Diego & Imperial Counties Labor Council, AFL-CIO". Both are as printed.

### Tax rate statement or fiscal analysis

None is printed for Measure A in S1. A charter amendment that is not a bond has no tax rate statement. I found no County fiscal analysis in S1 or on sdvote.com. The only cost claim in the guide comes from the proponents' argument ("Absolutely NO COST to TAXPAYERS."). That is an argument, not an official finding.
