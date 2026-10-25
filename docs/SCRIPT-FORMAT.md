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
credit = "..."                       # optional: a short form for under a chart; defaults to publisher
url = "..."
file = "sources/analysis.html"       # the archived copy, relative to the contest dir
retrieved = "2026-10-24"
```

Allowed source kinds (STANDARD.md section 1): `official-title-summary`,
`official-fiscal-analysis`, `official-argument`, `official-text`,
`candidate-statement`, `candidate-website`, `public-record`,
`official-report`, `official-data`.

`official-report` (a nonpartisan fiscal office's report or handout) and
`official-data` (a published data file from one) are background-only
(STANDARD.md rule 6.1): a line or chart may cite them only in a
`background` section.

## script.toml

```toml
contest = "ca-2026-11-03-prop-2"     # must match sources.toml
template = "measure"
template_version = 2
standard_version = 2

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

A line may carry one chart, shown while that line is narrated:

```toml
[section.line.visual]
kind = "bars"                        # bars | share | series | figure
title = "Rainy Day Fund target"      # shown above the chart
source = "lao-analysis"              # one id from sources.toml, named under the chart
unit = "%"                           # appended to each value label; may be ""
labels = ["Today", "Proposition 2"]
values = [10, 20]
```

- `bars`: one bar per label, from zero. `values` are numbers >= 0, one
  per label.
- `share`: one bar divided into parts, one per label; `values` are
  numbers >= 0 summing to at most 100 (percent of the whole).
- `series`: a line over time; `labels` are the x positions (years, as
  strings, evenly spaced) and `values` the numbers, one per label.
- `figure`: a fixed drawing with no numbers, named by `figure` (for
  example `figure = "steady-spending-volatile-revenue"`); no `labels`,
  `values` or `unit`. The template defines which figures exist.

A visual's `source` must also be among the line's `sources`.

### The measure template, version 2

Sections, in this order: `what`, any number of `background` sections
(zero or more, each with its own heading), `today`, `change`, `fiscal`,
the two sides, `vote`. Background sections tell the story behind the
contest (STANDARD.md section 6). Charts may appear in any section but
the sides (STANDARD.md rule 7.3).

### The measure template, version 1

Sections, in this order: `what`, `today`, `change`, `fiscal`, the two
sides, `vote`. A version 1 script fails the standard-version check
under Standard 2. The rest of this section applies to both versions. The sides are `yes` (with `side = "yes"`) and `no` (with
`side = "no"`). Which side plays first is decided at render time by a
stable hash of the contest id (STANDARD.md rule 2.4): the SHA-256 of
the UTF-8 contest id, `yes` first when its first byte is even and `no`
first when it is odd (`ballotreels.side_order`). The script file always
lists `yes` then `no`. Their word counts must be within 5% of
each other.
