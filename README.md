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
