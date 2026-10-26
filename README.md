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
