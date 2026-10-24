# Contest data format

Each contest lives in `data/<election>/<contest>/` with three parts:

- `sources/`: the archived copies of every source document.
- `sources.toml`: the contest's identity and its source manifest.
- `script.toml`: the narration script.

## sources.toml

```toml
[contest]
id = "ca-2026-11-03-prop-2"          # unique, stable; the cache key's contest id
election = "ca-2026-11-03"
division = "ocd-division/country:us/state:ca"
kind = "measure"                     # or "race"
title = "..."

[[source]]
id = "lao-analysis"                  # what script lines cite
kind = "official-fiscal-analysis"    # must be an allowed kind, below
publisher = "..."                    # who issued it, as shown on the sources card
url = "..."
file = "sources/analysis.html"       # the archived copy, relative to the contest dir
retrieved = "2026-10-24"
```

Allowed source kinds (STANDARD.md section 1): `official-title-summary`,
`official-fiscal-analysis`, `official-argument`, `official-text`,
`candidate-statement`, `candidate-website`, `public-record`.

## script.toml

```toml
contest = "ca-2026-11-03-prop-2"     # must match sources.toml
template = "measure"
template_version = 1
standard_version = 1

[[section]]
id = "what"                          # the template fixes which ids exist, in order
heading = "What it is"               # shown on screen
side = "yes"                         # only on side sections; see below

[[section.line]]
text = "One sentence, or two short ones, narrated as written."
sources = ["lao-analysis"]           # ids from sources.toml; or instead:
connective = true                    # a line that makes no claim
```

A line has `sources` (non-empty) or `connective = true`, never both.

### The measure template, version 1

Sections, in this order: `what`, `today`, `change`, `fiscal`, the two
sides, `vote`. The sides are `yes` (with `side = "yes"`) and `no` (with
`side = "no"`). Which side plays first is decided at render time by a
stable hash of the contest id (STANDARD.md rule 2.4): the SHA-256 of
the UTF-8 contest id, `yes` first when its first byte is even and `no`
first when it is odd (`ballotreels.side_order`). The script file always
lists `yes` then `no`. Their word counts must be within 5% of
each other.
