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

A line may carry one visual: a chart, a timeline or an illustration.
The centre of the frame shows only pictures: text that belongs to a
picture (a chart's title, its labels, its source line) is fine, but no
visual is only text. A visual appears as the line is narrated and
stays up through the lines after it in the same section, until a later
line brings its own visual or the section ends.

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
  numbers >= 0 summing to at most 100 (percent of the whole). One part
  is fine: it shows "this much of the whole".
- `series`: a line over time; `labels` are the x positions (years, as
  strings, evenly spaced) and `values` the numbers, one per label.
- `figure`: a fixed drawing with no numbers, named by `figure` (for
  example `figure = "steady-spending-volatile-revenue"`); no `labels`,
  `values` or `unit`. The template defines which figures exist.

```toml
[section.line.visual]
kind = "timeline"        # dated entries in a column, revealed one per line
source = "lao-volatility"
labels = ["1980 to 2014", "2014"]           # the dates
items = ["The state saved very little", "Voters set up today's rules"]

[section.line.visual]
kind = "illustration"    # a pencil drawing of the topic, from the library
name = "save-more"       # no source: the line cites
```

- `timeline`: `labels` (the dates) and `items` (what happened), the same
  number of each and at least 2. The entries appear one per line: the
  first with the line that carries the timeline, the next with the
  following line of its section, and so on; if the section runs out of
  lines, the rest appear with its last line. No `title`.
- `illustration`: a picture of the line's topic when there is no data
  to chart. `name` is an entry in the illustration library,
  `film/illustrations/illustrations.toml`, and its file must exist.
  Every entry is a pencil sketch made once with an image model in the
  manifest's one style, approved by a person and checked in; the
  library grows as new topics need pictures. No `title` and no
  `source`: an illustration carries no facts, and the line's own
  sources cover what is said.

The `number` and `words` kinds of earlier versions only showed text;
the check fails a script that uses either, and says to use an
illustration or a chart instead.

Every visual but an illustration has a `source`, which must also be
among the line's `sources`. Everything a visual shows (titles, labels,
items) is held to the judgment-word check, like the narration.

### The measure template, version 2

Sections, in this order: `what`, any number of `background` sections
(zero or more, each with its own heading), `today`, `change`, `fiscal`,
the two sides, `vote`. Background sections tell the story behind the
contest (STANDARD.md section 6). Visuals may appear in any section. In
the sides (STANDARD.md rule 7.3), a chart or timeline only when both
sides have one of the same kind, and an illustration only when both
sides have the same number of them.

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
