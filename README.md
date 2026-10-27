# ballotreels

Even-handed explainer videos for everything on your ballot.

Enter your address, see the districts you vote in, and get one short
video per race and measure on your ballot. Each video explains what the
contest is and what each side or candidate says, with every claim
sourced to an official or primary document, the same structure and
airtime for every side, and no judgment in the narrator's voice.

Videos are cached per contest, not per user: a statewide measure is
explained once, for everyone in the state.

- [docs/STANDARD.md](docs/STANDARD.md): the even-handedness standard
  every video must meet.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how a location becomes
  a set of videos, and where the data comes from.

Videos are made with [videobuilder](https://mgalgs.io/videobuilder/).

Status: early prototype, piloting on California.

## Checking a contest

Each contest lives in `data/<election>/<contest>/`
([docs/SCRIPT-FORMAT.md](docs/SCRIPT-FORMAT.md)). To run the
standard's machine checks on one or more contests (Python 3.11+, no
dependencies):

    python -m ballotreels check data/ca-2026-11-03/prop-2

It prints each failure on its own line and a summary per contest, and
exits 0 only if every contest passes. To run the tests:

    python -m unittest

## Rendering a contest

Videos are built with [videobuilder](https://mgalgs.io/videobuilder/), a
separate project. Set up a venv that can see it (it needs system packages
of its own — see its README):

    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install '<path to a videobuilder checkout>[speech]'

Narrating a contest is a two-step, mostly-offline process. First, export
its script as plain narration text:

    python -m ballotreels narration data/ca-2026-11-03/prop-2

This writes `narration.txt` in the contest's directory: each script
line's text, one per line, in the order the video will play them (the
two side sections ordered by `ballotreels.side_order`). Then turn it
into audio with videobuilder's Chatterbox engine, which runs in its own
Python (videobuilder's README has the install):

    python -m videobuilder say data/ca-2026-11-03/prop-2/narration.txt \
        --engine chatterbox --voice voices/narrator.wav --gap 0.6 \
        --out data/ca-2026-11-03/prop-2/narration.wav

`voices/narrator.wav` is the narrator's voice: Chatterbox speaks in the
voice of that clip. It is Kokoro's `am_michael` voice reading two
sentences, chosen for a plain, neutral delivery. Every video uses it
(STANDARD.md rule 4.1).

`scripts/narrate.sh <contest-dir>...` runs both steps, and finds the
Chatterbox interpreter at `~/.local/chatterbox/bin/python` unless
`VIDEOBUILDER_CHATTERBOX_PYTHON` says otherwise. Chatterbox, not
Kokoro: Kokoro mis-phrases long noun-phrase subjects, and fixing that
by rewording the script or adding break marks is not an option, since
the script must say what the sources say.

This writes `narration.wav` plus its `.vtt`/`.json` sidecars beside it;
commit all three along with `narration.txt`. Re-run `narration` and `say`
together whenever `script.toml` changes, so the sidecars stay in sync —
`python -m ballotreels check` includes an airtime check that reads them
when they're present, and a stale pair is reported as a `NarrationError`
if the render template is asked to use them.

With narration committed, render the contest's video (both the 9:16
phone-reel format and the 16:9 format, by default):

    python -m ballotreels render data/ca-2026-11-03/prop-2 --format all

This writes `out/<contest-id>-<format>.mp4` using the one measure video
template, `film/measure.py`, which reads the contest directory and its
committed narration — nothing about one contest is in the template
itself.

## Extending the contest index

Each election's ballot is listed in `data/<election>/contests.toml`
(docs/ARCHITECTURE.md). To add California's statewide measures from the
Secretary of State's official voter information guide:

    python -m ballotreels measures ca-sos data/ca-2026-11-03

It fetches each proposition's own overview page, starting from
`--start` (default `1`), and appends any measure not already in the
index; an entry already there (titled by hand, or from an earlier run)
is left untouched. `--base-url` overrides the Secretary of State's site
(default `https://voterguide.sos.ca.gov`), for pointing at an archived
copy.

## Building the geo lookup data

The site needs a zip-to-district lookup and simplified district shapes,
built from free Census sources (docs/ARCHITECTURE.md) into a
git-ignored data directory:

    python -m ballotreels geo build --state ca

This downloads Census TIGER/Line shapefiles (congressional, state
senate, state assembly and county boundaries, plus ZCTA zip-code
shapes; each a `.zip` archive, whose `.shp` and `.dbf` it extracts)
and the ZCTA-to-congressional-district and ZCTA-to-county relationship
files, then writes `<data-dir>/geo/<state>/`: one simplified GeoJSON file per
district kind, one per zip outline, and a `zips.json` lookup table. It
is safe and idempotent to re-run: a file already downloaded is not
re-fetched, and the build only replaces the previous output once it has
fully succeeded.

Flags: `--state` (a two-letter abbreviation, default `ca`; only `ca` is
tested), `--data-dir` (default `$BALLOTREELS_DATA_DIR` or `<repo>/var`),
`--min-overlap` (drop a zip/district overlap smaller than this fraction
of the zip's land area; default `0`, keep every sliver), `--tolerance`
(Douglas-Peucker simplification tolerance in degrees; default `0.001`),
and `--url NAME=URL` (repeatable, overrides one download by name, e.g.
`--url cd.zip=https://...`, for when a Census URL has moved). The names
are `cd.zip`, `sldu.zip`, `sldl.zip`, `county.zip`, `zcta.zip`,
`cd_rel.txt`, `county_rel.txt`, `sldu_rel.txt` and `sldl_rel.txt`.

The ZCTA-to-state-legislative-district relationship files
(`sldu_rel.txt`, `sldl_rel.txt`) default to the 2024-district files
under `rel2020/cd-sld/`, but those URLs have not been checked against
census.gov. If a default one fails to download (or is not a
relationship file), the build still succeeds but prints a warning, and
a zip lookup carries no district of that kind (the district shapes are
still built, and the address lookup still resolves it exactly). Pass
`--url sldu_rel.txt=...` / `--url sldl_rel.txt=...` to supply a file in
the same pipe-delimited format (`GEOID_ZCTA5_20`, a `GEOID_*` district
column, `AREALAND_PART`); a URL given that way must work.

Look up what a zip code resolves to:

    python -m ballotreels geo zip 90001 --state ca --data-dir var

## Running the serve tier

The serve tier is two listeners in one process: a public one (the site
and its API) and a private one (the worker API and the queue monitor),
meant to sit on opposite sides of a private tunnel (the brief: a
DigitalOcean droplet talking to a home cluster over WireGuard
site-to-site).

    BALLOTREELS_TOKEN=<a long random string> python -m ballotreels serve

`BALLOTREELS_TOKEN` is required: without it (or with only whitespace),
`serve` refuses to start at all, since the private listener would
otherwise be unguarded. Both listeners default to loopback addresses;
put a real address only in your own deployment configuration, never in
this repository.

| Flag | Environment variable | Default |
|---|---|---|
| `--data-dir` | `BALLOTREELS_DATA_DIR` | `<repo>/var` |
| `--election` | `BALLOTREELS_ELECTION` | the only election under `data/`, if there is just one |
| `--public-host` | `BALLOTREELS_PUBLIC_HOST` | `127.0.0.1` |
| `--public-port` | `BALLOTREELS_PUBLIC_PORT` | `8080` |
| `--private-host` | `BALLOTREELS_PRIVATE_HOST` | `127.0.0.1` |
| `--private-port` | `BALLOTREELS_PRIVATE_PORT` | `8081` |
| (none) | `BALLOTREELS_TOKEN` | required; the shared bearer token for the private listener |
| `--generate-limit` | `BALLOTREELS_GENERATE_LIMIT` | `5` |
| `--generate-window` | `BALLOTREELS_GENERATE_WINDOW` | `3600` (seconds) |
| `--trust-forwarded-for` | `BALLOTREELS_TRUST_FORWARDED_FOR` | off; set only behind a trusted reverse proxy |
| `--heartbeat-timeout` | `BALLOTREELS_HEARTBEAT_TIMEOUT` | `120` (seconds) |
| `--eta-default-minutes` | `BALLOTREELS_ETA_DEFAULT_MINUTES` | `10` |
| `--max-upload-mb` | `BALLOTREELS_MAX_UPLOAD_MB` | `500` |
| `--geocoder-url` | `BALLOTREELS_GEOCODER_URL` | the Census Geocoder |

`--generate-limit` and `--generate-window` bound how many videos one
client IP may start generating in a rolling window (joining an
already-queued or already-cached contest is always free). The queue
monitor lives on the private listener at `/admin/`, signed in with the
same token (as a cookie, via `/admin/login`, so a phone browser can use
it too).

## Running a worker

A worker claims jobs from the serve tier's private listener, runs them
(sources, script, check, narrate, render, encode), and uploads the
result. It needs its own checkout of this repository (for
`scripts/narrate.sh`, the renderer, and the contest's sources and
script) and, for a real render, the same `videobuilder` setup as
"Rendering a contest" above.

    BALLOTREELS_TOKEN=<the same token> \
        python -m ballotreels worker --server http://<private-listener-host>:8081

| Flag | Environment variable | Default |
|---|---|---|
| `--server` | `BALLOTREELS_SERVER` | required: the serve tier's private listener URL |
| (none) | `BALLOTREELS_TOKEN` | required; the same token the serve tier uses |
| `--repo` | — | this repo |
| `--worker-id` | — | `<hostname>-<pid>` |
| `--runner` | — | `subprocess` (`fake` is for tests and CI) |
| `--work-dir` | — | `<data-dir>/work` |
| `--masters-dir` | `BALLOTREELS_MASTERS_DIR` | `<repo>/var/masters` |
| `--ffmpeg` | `BALLOTREELS_FFMPEG` | `ffmpeg` on `PATH` |
| `--crf` | `BALLOTREELS_CRF` | `18` |
| `--maxrate` | `BALLOTREELS_MAXRATE` | `1500k` |
| `--poll-interval` | — | `2` seconds between claim attempts when idle |
| `--heartbeat-interval` | — | `10` seconds between heartbeats |
| `--once` | — | claim and work at most one job, then exit |

The worker renders a full-quality master locally and keeps it at
`--masters-dir` once its job is done (a later run of the same contest
overwrites it); a job that fails, is cancelled or is released deletes
its master. It encodes a web copy with `ffmpeg` (H.264/yuv420p/AAC, `+faststart`)
plus a poster JPEG, per the operator's decision on serving media. `--crf`
18 was chosen by rendering the real Prop 2 contest and measuring the
encoded bitrate at several CRF values (see the commit history); raise
it if a future, busier template needs a smaller file.

### Storage: where an uploaded video goes

`BALLOTREELS_STORAGE` selects the worker's upload backend:

- `local` (default): uploads through the serve tier's own worker API;
  the serve tier stores the files under its data directory and serves
  them with Range support.
- `s3`: uploads straight to an S3-compatible bucket (DigitalOcean
  Spaces), signed with a stdlib implementation of AWS Signature Version
  4 — the serve tier never sees the video bytes, only the object URLs
  the worker reports back. Requires every one of:

  - `BALLOTREELS_S3_ENDPOINT` (e.g. `https://<region>.digitaloceanspaces.com`)
  - `BALLOTREELS_S3_REGION`
  - `BALLOTREELS_S3_BUCKET`
  - `BALLOTREELS_S3_PUBLIC_BASE` (the CDN base URL videos are served from)
  - `BALLOTREELS_S3_ACCESS_KEY_ID`
  - `BALLOTREELS_S3_SECRET_ACCESS_KEY`

  and optionally `BALLOTREELS_S3_PREFIX` (default `ballotreels`). The
  worker exits immediately, naming every variable that is missing, if
  `BALLOTREELS_STORAGE=s3` is set without all of them.
