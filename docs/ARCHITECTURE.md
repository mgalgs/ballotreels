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
   not built in this round.
5. **Checks.** The machine checks in the standard run on the script,
   and again once narration exists (airtime can only be measured then).
   A failure fails the job with the check's output, shown to the
   operator on the queue monitor; nothing is published that fails a
   check.
6. **Render.** A fixed videobuilder film template per contest kind
   (measure, candidate race) reads the script, narrates it with
   videobuilder's speech module (one voice for all), and draws the cards
   and the closing sources card. A soft drawing sound, cut from two short
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
against the serve tier's job queue.

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
