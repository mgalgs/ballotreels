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

    location ─▶ divisions ─▶ contests ─▶ sources ─▶ script ─▶ checks ─▶ render ─▶ encode ─▶ cache

1. **Location to divisions.** An address resolves to an exact set of
   divisions. A zip code may span several, so the UI shows a map of the
   candidate districts and asks the user to pick, or to enter an address.
   A zip's cities and school districts are never asked about: the ballot
   lists every one overlapping it, marking those that cover only part
   of it (see "Local contests" below).
2. **Divisions to contests.** For each division, the contests on this
   election's ballot.
3. **Sources.** For each contest, fetch and archive the primary
   documents it may cite (see the standard, section 1). Each gets a
   stable source id.
4. **Script.** A pluggable script writer turns the archived sources into
   a structured script: the contest kind's fixed sections, each
   sentence tagged with the source ids it rests on or marked connective.
   Today's only writer returns the contest's hand-written `script.toml`,
   or fails plainly if there is none yet; a script writer that drafts
   one automatically (a language model, or otherwise) is future work,
   not built in this round. A script records the questions a reader
   asked of it and the lines that answer each (STANDARD.md section 10,
   `[[question]]` in SCRIPT-FORMAT.md).
5. **Checks.** The machine checks in the standard run on the script,
   and again once narration exists (airtime can only be measured then).
   A failure fails the job with the check's output, shown to the
   operator on the queue monitor; nothing is published that fails a
   check.
6. **Render.** A fixed videobuilder film template per contest kind
   (measure, candidate race) reads the script, narrates it with
   videobuilder's speech module (one voice for all), and draws the cards
   and the closing sources card. A yes/no measure's two sides share one
   slide; a choice question (STANDARD.md section 8) has no sides, and
   draws every option, in ballot order, on one grid of equal cells (more
   than six: several grid pages), with the options listed on its card. A soft drawing sound, cut from two short
   recordings of a pencil and a felt-tip marker (film/draw_sound.py,
   film/sounds/) rather than synthesized, follows the pencil or
   highlighter while it is actually drawing, levelled about 13.5 dB under
   the narration's own RMS. The
   on-screen-time check runs on the rendered timeline.
7. **Encode.** The worker keeps the full-quality render (the "master")
   to itself and makes a smaller web copy with ffmpeg (H.264/yuv420p/
   AAC, `+faststart`) plus a poster frame, sized for a phone on cellular
   data.
8. **Cache.** The web copy, poster, script, and source archive are
   stored under the cache key and served from there on every later
   request.

Steps 1-2 and 8 run on the serve tier; steps 3-7 run on a worker, in a
scratch copy of the contest (never the worker's own committed copy),
against the serve tier's job queue. The copy keeps the contest's
committed narration: one narrated from exactly the current script was
made and transcript-checked on the host, so the worker uses it as it
is and never asks the TTS again. A stale one fails the job, asking for
it to be re-narrated on the host: the worker never re-makes a committed
narration, since `say` re-speaks an edited line and the unchanged line
after it (its context), and any new take can fail the transcript check.

## Local contests

A ballot's divisions run from widest to narrowest: the state, the
congressional district, the state senate and house (or assembly)
districts, then the local ones: the **county**, the **city** and the
**school district**. The site lists them the other way round, most
local first, with a special district's measures ahead of its county's.
Their OCD-IDs are the state's followed by the level and the name, lower
case, spaces as underscores, nothing but letters, digits and `. _ ~ -`:

    ocd-division/country:us/state:ca/county:san_diego
    ocd-division/country:us/state:ca/place:san_diego
    ocd-division/country:us/state:ca/school_district:san_diego_unified_school_district

A city is a TIGER/Line incorporated place (a census-designated place
has no government, and so no measures); its name is TIGER's (`San
Diego`, shown as "City of San Diego"). A school district is a unified,
elementary or secondary one, named as TIGER names it ("San Diego
Unified School District"); an address in both an elementary and a
secondary district is in both.

Local contests live in the state's election directory beside the
statewide ones, listed in its `contests.toml` like any other, with
their own division: the same election, the same ballot. A contest's id
starts with its jurisdiction, so its directory name is unique and
readable (`sd-county-measure-a`, `san-diego-city-measure-b`,
`helix-water-measure-c`), and local measure numbers are letters.

**Zips.** The Census publishes ZCTA relationship files for
congressional districts and counties but none for cities or school
districts, so `geo build` measures each zip's share of every city and
school district from the shapes themselves, along horizontal lines
about 220 m apart. A district covering under 1% of a zip is left off it
(the zip and district outlines come from different years' boundaries,
which may disagree by a sliver); one covering under 99% of it is
listed in the zip's `partial`. A zip split between counties asks which,
as for any district; a zip's cities and school districts are not asked
about. The ballot lists the contests of every one overlapping the zip,
and those of a `partial` one say "May be on your ballot, depending on
your address." An address resolves them exactly (the Census Geocoder's
incorporated places and school district layers), so its ballot marks
none.

**Special districts.** A water, fire, health care, community services
or community college district has no free statewide boundary layer.
Its contest's division is its county, and its `sources.toml` names who
votes on it in `voters` ("the Helix Water District"): the site's ballot
and contest page and the film's card say "Only voters in the Helix
Water District vote on this.", so no one takes it for a measure every
voter in the county gets. A county's own measure has an id of the form
`<county>-county-measure-<letter>`; any other measure under a county
must have `voters`, which both `check` and the contest index enforce
(docs/SCRIPT-FORMAT.md).
A district that crosses county lines gets one contest per county it
reaches, each under its county and with the same `voters`
(`sierra-ccd-measure-x-placer`, `sierra-ccd-measure-x-nevada`): a
contest has one division, and one filed under a single county is
missing from every other county's ballots.

The crash course stays statewide: its members are the state's own
measures, never a local one.

## The crash course

A state's **crash course** is one video through every statewide measure
on its ballot, so a voter can watch one thing; it sits at the top of the
state's page (`/<st>/<year>` and `/<st>`) once it has been made, with a
chapter chip per measure, and the page is otherwise unchanged.

It says nothing new. Its members are the election's statewide measures
(kind `measure`, division the state's) in `contests.toml`'s order, the
ballot's, set out as a contact sheet: pages of up to six tiles (two
columns by three rows in 9:16), split as evenly as they go over the
fewest pages (fourteen measures make pages of 5, 5 and 4, not 6, 6 and
2). Each page is headed with the state's name and "statewide measures",
with "1 of 3" when there are several. A tile shows the measure's badge
and number as its card draws them ("PROP 3"), its short title (its
`contests.toml` title less the designation the badge shows, cut at two
lines with an ellipsis), its one-liner, and, small, the measure's own
page (`ballotreels.org/<st>/<year>/<measure>`), where its full video is.

The one-liner is a line of the measure's own script, verbatim: the
first line of its `change` section, what the measure would do, or, in a
script with no `change` section, the first line of its opening section
(`what`). It is never a side's argument. Its sound is that line's cut
of the member's committed `narration.wav`, by its `narration.json`
phrase timings, a tenth of a second either side of the words (never
past halfway to the phrase before or after); the TTS is never asked for
anything. Tiles are drawn on one at a time, in the coloured-pencil
style, while their one-liner is said; earlier tiles on the page stay,
and the next page comes on clean. Every tile is the same size, drawn
the same way, with its one-liner in the same type: the largest at which
every member's fits. There is no caption: the tile writes out the words
it says.

Each tile's slot lasts as long as its one-liner's cut plus half a
second. No slot is padded out to match a longer one, so a page is as
long as a second's lead for its heading and its slots together. Before
the first page, an opening card, on screen only, gives the state's
name, "N statewide measures" and the election's date; after the last,
a closing page, still and silent for three seconds, says that every
measure has its own one-minute video, over the state's page; then a
sources card lists what the one-liners cite, grouped under each
measure's title, over as many pages as it takes. The link under the
stage on every frame is the state's page, `ballotreels.org/<st>/<year>`.
Its chapters are one per measure, each starting where its slot does,
titled as `contests.toml` titles it.

The film also has a 16:9 layout, for a YouTube copy rendered from the
command line only (`render <election-dir> --format 16x9`); the pipeline
renders and serves 9:16 alone, so the 16:9 copy is in no cache key. It
has the same frames, audio and chapters: its pages of tiles are three
columns by two rows, the opening card and closing page are laid out for
landscape, and the sources card has 9:16's pages, a page's groups set
in two columns when it has more than one. The drawing sounds follow the
9:16 strokes, as the measure film's do; the 16:9 strokes land within a
few frames of them.

It is an election-level contest of its own kind (`crash-course`): id
`<election>-crash-course`, division the state, derived by the index
loader (`ContestIndex.crash_course`) for any election with at least two
statewide measures, never listed in `contests.toml`. Its template
(`film/crash_course.py`) has its own version. Its cache key's contest
part is `<election>-crash-course@<digest>`, the digest hashing every
member's `script.toml`, `sources.toml`, `narration.json` and
`narration.wav`, so a change to any member is a new key, and an older
crash course is never shown beside measure videos it disagrees with.

The operator queues it like any contest: `POST /api/generate` with its
id, approved in the queue monitor, under the same per-IP and global
limits. The worker copies the election's `contests.toml` and every
member's directory into its scratch directory and runs the usual stages
over them: each member's sources and checks; the job's digest checked
against the worker's own copy (a worker whose checkout differs from the
serve tier's fails rather than render other words); and in place of
narrating, each member's committed narration must be current for its
script. A missing or stale one fails the job with a message naming the
measure, the same rule as for a single measure, except that a missing
narration is not made here either. The published `script.toml` is a
derived record of the reused lines, and the published sources name the
measure each is cited for.

## Data sources (pilot: California, free sources only)

The pilot covers federal, state-legislative and statewide contests,
and local measures (county, city, school district and special
district) from each county's own official sources, added by hand per
county.

| Need | Source |
|---|---|
| District shapes for the map | Census TIGER/Line: congressional districts, state legislative districts (upper and lower), counties, incorporated places, unified, elementary and secondary school districts |
| Address to districts | Census Geocoder (free, no key; returns the districts above for an address). Google Civic Information divisions endpoint as a cross-check and for OCD-IDs |
| Zip to candidate districts | Census ZCTA relationship files, intersected with the TIGER shapes; for cities and school districts, which have none, the ZCTA shapes measured against theirs |
| Statewide measures: title, summary, text, fiscal analysis, arguments | California Secretary of State official voter information guide (the analysis there is the Legislative Analyst's Office's) |
| Certified candidate list, ballot designations | California Secretary of State certified list of candidates |
| Federal candidates, filings | FEC API |
| State legislators, voting records | Open States |

Every source is fetched by a per-source adapter that writes a normalized
contest record plus the archived documents, so adding a paid source
later is one more adapter, not a rewrite.

## Where a finished video lives

A worker's render is a full-quality master it never uploads; only the
web-encoded copy and poster leave the worker, behind a storage
interface with two backends (`BALLOTREELS_STORAGE`):

- `local` (the default): the worker uploads to the serve tier's own
  worker API, which stores the files under its data directory and
  serves them directly.
- `s3`: the worker uploads straight to an S3-compatible bucket
  (DigitalOcean Spaces), signed with a stdlib AWS Signature Version 4
  implementation, then tells the serve tier the object's CDN URLs; the
  serve tier never sees the video bytes in this mode.

## Serving: a public tier and a pull worker

The product is two processes sharing one SQLite job queue and video
cache, plus the operator's queue monitor:

- **The serve tier** (`python -m ballotreels serve`) is meant to run on
  a small public host (a DigitalOcean droplet in the operator's plan).
  It has two listeners:
  - the **public** listener: the site, the district/zip/address lookup,
    the ballot and contest APIs, Generate, and the cached videos
    (served with HTTP Range support, since Safari and iOS require it).
  - the **private** listener: the worker API and the queue monitor,
    bound to its own address (in the operator's deployment, the
    WireGuard interface to the home cluster) and guarded by a shared
    bearer token. It refuses to start without one.
- **A worker** (`python -m ballotreels worker`) runs wherever the real
  generation work happens (the operator's home cluster, over a
  WireGuard site-to-site tunnel to the droplet). It **pulls**: it polls
  the private listener to claim the next queued job, works it locally
  in a scratch copy of the contest, and uploads the result; the home
  side never needs an inbound connection. Several workers may run at
  once, each job claim is atomic, and a worker that stops sending
  heartbeats (crashed, lost network) has its job returned to the queue
  after a configurable timeout, not left stuck.
- A second request for a contest already queued or running joins that
  job instead of starting another; a contest already cached returns
  the cached video immediately. A per-client-IP limit bounds how many
  new jobs a Generate request may create (joining or reading a cached
  video is never limited).
- **The queue monitor**, on the private listener, lists every job with
  its state, current stage, per-stage timestamps, worker id, last
  heartbeat and error output, and lets the operator retry, cancel or
  requeue one; it also shows queue depth and the median job time, which
  the ETA shown to voters is based on.
- **Corrections** (STANDARD.md rule 5.2) are fixed by regenerating: the
  operator fixes the contest's script or sources, adds a
  `[[contest.correction]]` note to the contest index, and presses
  "regenerate" on the contest's done job in the queue monitor. That
  queues a new job for the same cache key; the old video keeps serving
  until the new one completes and replaces it. Each job's files are
  published under a path that includes the job id
  (`/v/<hash>/<job-id>/video.mp4` locally,
  `<prefix>/<hash>/<job-id>/<name>` in the bucket), so a regenerated
  video gets a new URL, and the year-long `immutable` caching of the old
  one in browsers and the CDN never hides the fix. A retried upload of
  the same job still overwrites its own objects. Superseded objects in
  the bucket are not deleted.
- No accounts: the public site asks for nothing but a zip code or an
  address, and the operator's queue monitor is the only gated page,
  signed in with the one shared token.

## Scope of this round

- California, the 2026-11-03 general election, used as test data; the
  first real target is the next election cycle.
- One contest end to end first: a statewide measure, since its sources
  are the most complete and most official. Candidate races appear in
  the contest index but have no script template yet, so the site shows
  them as not available rather than generating anything.
- Deployment itself (the droplet, the WireGuard tunnel, cluster
  manifests) is a later step with the operator; this round is the
  software that runs on both sides of it.
