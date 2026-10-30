# Measure Q — City of Richmond (Contra Costa County), November 3, 2026

Retrieved 2026-10-28. **Not archived — no official document found.**

Tried: the City's sitemap (<https://www.ci.richmond.ca.us/sitemap.xml>; no 2026 measure page), the City Clerk page (<https://www.ci.richmond.ca.us/1340/City-Clerk>; no election links), and an AgendaCenter search (no results returned to a plain GET). The county guide is blocked (contracostavote.gov).

## Ballot question — UNCONFIRMED

Finder text (cocotax.org; not a source). General obligation bond, $120,000,000:

> To support rapid, 911 emergency medical response, modernize and rehabilitate unsafe/deteriorating firefighter housing and facilities, including mold/asbestos abatement/removal, replace electrical systems, leaky pipes/roofs, and improve structure resiliency during disasters, shall the City of Richmond’s measure authorizing $120,000,000 in bonds at legal rates, levying an estimated average tax rate of $22.15/$100,000 of assessed valuation, averaging $7,568,158 annually while bonds are outstanding, requiring citizen oversight, audits, and spending only on approved projects, be adopted?

## Missing

Everything: City Council resolution/ordinance, City Attorney's impartial analysis, tax rate statement, arguments and rebuttals.

## Feed documents retrieved 2026-10-30

```
Measure Q — City of Richmond, November 3, 2026 General Election
Retrieved 2026-10-30. All files from the City of Richmond's own CivicPlus DocumentCenter,
linked from the official election page https://www.ci.richmond.ca.us/4988/2026-GENERAL-ELECTION-INFORMATION
(the city site is not blocked; only the direct /sitemap root path required finding this
specific page via search — DocumentCenter/View/<id> links work directly, no bot challenge).

ordinance-12-26.pdf
  "An ordinance of the City Council of the City of Richmond ordering the submission of a
  proposition of incurring a bonded indebtedness..." Ordinance No. 12-26 N.S., adopted
  2026-07-28 (conformed/signed copy). Contains the full text of the Measure (ballot
  proposition language and bond authorization) as Exhibit A.
  https://www.ci.richmond.ca.us/DocumentCenter/View/80525/12-26-NS-ordering-submission-of-a-General-Obligation-Bond-Measure---CONFORMED---Adopted-7-28-26

resolution-143-26.pdf
  Resolution No. 143-26, "A Resolution of the City Council of the City of Richmond placing a
  Measure to authorize the City of Richmond to issue General Obligation Bonds at the General
  Municipal Election to be held on November 3, 2026...", adopted 2026-07-28, signed by
  City Clerk Pamela Christian. Section 1 gives the official ballot question verbatim
  (matches the text already in the README). Sections 5-9 set the impartial-analysis and
  argument/rebuttal filing deadlines.
  https://ca-richmond3.civicplus.com/DocumentCenter/View/80526/143-26-CC-reso-Ballot-Measure-Fire-Stations-Nov-3-2026-General-Election--CONFORMED---Adopted-7-28-2026

impartial-analysis.pdf
  City Attorney's impartial analysis of Measure Q (Elections Code § 9280).
  https://www.ci.richmond.ca.us/DocumentCenter/View/80652/City-Attorney-Impartial-Analysis---FINAL_775101_-WITH-ASSIGNED-LETTER

tax-rate-statement.pdf
  Finance Director's impartial financial analysis / tax rate statement for the G.O. bond
  (Elections Code § 9401 / City Municipal Code 2.16.070).
  https://www.ci.richmond.ca.us/DocumentCenter/View/80651/IMPARTIAL-FINANCIAL-ANALYSIS-_GO_Bond_Measure__EC_81126-WITH-ASSIGNED-LETTER

argument-in-favor.pdf
  Argument in favor of Measure Q, submitted 2026-08-17.
  https://www.ci.richmond.ca.us/DocumentCenter/View/80727/ARGUMENT-IN-FAVOR-MEASURE-Q---SUBMITTED-8-17-26

argument-against.pdf
  Argument against Measure Q.
  https://www.ci.richmond.ca.us/DocumentCenter/View/80726/Argument-Against-Richmond-Measure-Q

rebuttal-to-argument-in-favor.pdf
  Rebuttal to the argument in favor of Measure Q.
  https://www.ci.richmond.ca.us/DocumentCenter/View/80761/Rebuttal-to-Argument-in-Favor-Measure-Q-for-WEB

rebuttal-to-argument-against.pdf
  Rebuttal to the argument against Measure Q, submitted 2026-08-24.
  https://www.ci.richmond.ca.us/DocumentCenter/View/80762/REBUTTAL-TO-ARGUMENT-AGAINST-MEASURE-Q---SUBMITTED-8-24-26---FOR-WEB

Note: each DocumentCenter URL 302-redirects from the bare /View/<id> to /View/<id>/<slug>;
fetching the bare numeric URL with safe-http-get.sh returns only the redirect HTML (since it
does not follow redirects). The slug (and, for three of these files, a literal trailing
"?bidId=") had to be appended by hand, taken from the Location in the redirect body.
```
