# Architecture

ballotreels turns a location into a set of short explainer videos, one
per contest on that location's ballot. Every video must meet
[the even-handedness standard](STANDARD.md).

## The cache key is the contest, not the user

A **contest** is one race or one measure in one election. It belongs to
exactly one **division**: the jurisdiction that votes on it (the state,
a congressional district, a county, a city, a school district), named
by its [Open Civic Data division id](https://open-civic-data.readthedocs.io/en/latest/ocdids.html)
(OCD-ID), for example `ocd-division/country:us/state:ca/cd:12`.

A user's ballot is the union of the contests of every division they
fall in. A video is made the first time anyone needs it and served from
the cache after that, so the statewide measures are rendered once for
the whole state, not once per voter. Nothing is per-user.

A video's cache key:

    (election id, division OCD-ID, contest id, standard version, template version)

Bumping the standard or a template version makes every older video
stale; they are regenerated on next request.

## Pipeline

    location ─▶ divisions ─▶ contests ─▶ sources ─▶ script ─▶ checks ─▶ render ─▶ cache

1. **Location to divisions.** An address resolves to an exact set of
   divisions. A zip code may span several, so the UI shows a map of the
   candidate districts and asks the user to pick, or to enter an address.
2. **Divisions to contests.** For each division, the contests on this
   election's ballot.
3. **Sources.** For each contest, fetch and archive the primary
   documents it may cite (see the standard, section 1). Each gets a
   stable source id.
4. **Script.** A language model drafts the narration from the archived
   sources only, into a structured script: the contest kind's fixed
   sections, each sentence tagged with the source ids it rests on or
   marked connective.
5. **Checks.** The machine checks in the standard run on the script.
   A failure goes back to step 4 with the failures listed, a bounded
   number of times, then the contest is flagged for a human.
6. **Render.** A fixed videobuilder film template per contest kind
   (measure, candidate race) reads the script, narrates it with
   videobuilder's speech module (one voice for all), and draws the cards
   and the closing sources card. The on-screen-time check runs on the
   rendered timeline.
7. **Cache.** The MP4s, the script, and the source archive are stored
   under the cache key.

## Data sources (pilot: California, free sources only)

The pilot covers federal, state-legislative and statewide contests.
County, city and school contests need a paid sample-ballot source and
are out of scope until one is chosen.

| Need | Source |
|---|---|
| District shapes for the map | Census TIGER/Line: congressional districts, state legislative districts (upper and lower), counties, places |
| Address to districts | Census Geocoder (free, no key; returns the districts above for an address). Google Civic Information divisions endpoint as a cross-check and for OCD-IDs |
| Zip to candidate districts | Census ZCTA relationship files, intersected with the TIGER shapes |
| Statewide measures: title, summary, text, fiscal analysis, arguments | California Secretary of State official voter information guide (the analysis there is the Legislative Analyst's Office's) |
| Certified candidate list, ballot designations | California Secretary of State certified list of candidates |
| Federal candidates, filings | FEC API |
| State legislators, voting records | Open States |

Every source is fetched by a per-source adapter that writes a normalized
contest record plus the archived documents, so adding a paid source
later is one more adapter, not a rewrite.

## Scope of the pilot

- Single user, run locally. No public hosting, accounts or rate limits.
- California, the 2026-11-03 general election, used as test data; the
  first real target is the next election cycle.
- One contest end to end first: a statewide measure, since its sources
  are the most complete and most official.
