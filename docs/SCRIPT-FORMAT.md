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

### The card: the measure's official page

A script may open on a drawn copy of the top of the measure's page in
the official voter guide, and come back to it to "click" the terms on
it (the `page` visual, below). The optional top-level `[card]` table
quotes that page:

```toml
[card]
source = "quick-reference"   # a source of kind official-title-summary
number = "2"                 # drawn as the "PROP 2" badge
title = "INCREASES STATE’S RAINY DAY FUND. LEGISLATIVE CONSTITUTIONAL AMENDMENT."
origin = "Put on the Ballot by the Legislature"
summary = "Increases California's Rainy Day Fund, ... Fiscal Impact: State budget reserves would be higher."
yes = "A YES vote on this measure means: ..."
no = "A NO vote on this measure means: ..."
```

- All seven keys are required, each a non-empty string. `source` must be
  in `sources.toml`, of kind `official-title-summary`.
- **Verbatim**: `title`, `origin`, `summary`, `yes` and `no` must each
  appear in the archived source's text, compared after stripping its
  markup (and the contents of its scripts and styles), decoding
  entities, collapsing whitespace and ignoring whitespace before
  punctuation (the page renders as `Fiscal Impact : State`). Quotes and
  case are compared as they are: the title is upper-case, with a curly
  apostrophe, on the page. A failure names the field.
- The card is exempt from the judgment-word check: it is a verbatim
  official quote, not the narrator's voice (STANDARD.md rule 3.1).
  Everything else in the script keeps the check.
- The card has no supporters or opponents line and no arguments, on
  purpose: the arguments belong only to the side sections (rule 6.3),
  and the page's "Opponents: None submitted" sits beside a filed
  argument against.

A line may carry one visual: a chart, a timeline, a list, an
illustration or the page card. The centre of the frame shows only
pictures: text that belongs to a picture (a chart's title, its labels,
its source line) is fine, but no visual is only text. There are two
exceptions: the page card, which is a picture of the official ballot
document, as the ballot card is; and a `list`, a side's own points, in
short form, as a checklist. A visual appears as the line is narrated and
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
kind = "list"             # a side's own points, as a checklist
source = "arguments"
items = ["Stops overspending when there is a surplus", "Protects schools, health care and public safety in downturns"]

[section.line.visual]
kind = "illustration"    # a pencil drawing of the topic, from the library
name = "save-more"       # no source: the line cites
```

- `timeline`: `labels` (the dates) and `items` (what happened), the same
  number of each and at least 2. The entries appear one per line: the
  first with the line that carries the timeline, the next with the
  following line of its section, and so on; if the section runs out of
  lines, the rest appear with its last line. No `title`.
- `list`: a checklist of the side's own points, in short form: `items`,
  at least 1, each drawn with a hand-drawn check mark. No `title` and
  no `labels`: it is a `timeline` without dates, revealed one entry per
  line the same way. Allowed in any section, not only a side's.
  **Balance (rule 7.3):** if either side section has a `list`, both
  must, with the same number of items in all; a failure names both
  counts.
- `illustration`: a picture of the line's topic when there is no data
  to chart. `name` is an entry in the illustration library,
  `film/illustrations/illustrations.toml`, and its file must exist.
  Every entry is a pencil sketch made once with an image model in the
  manifest's one style, approved by a person and checked in; the
  library grows as new topics need pictures. No `title` and no
  `source`: an illustration carries no facts, and the line's own
  sources cover what is said.

```toml
[section.line.visual]
kind = "page"            # the card: the measure's official page
source = "quick-reference"   # must equal card.source, and be among the line's sources
focus = "Rainy Day Fund"     # optional: the term to click
```

- `page`: the `[card]`, drawn as the official page. Allowed only when
  the script has a card; no `title`. `focus`, if given, is a phrase
  that must occur in the card's text (its title, origin, summary, yes
  and no), matched case-sensitively, so `"Rainy Day Fund"` picks the
  summary's words over the upper-case title's. A highlighter pen
  sweeps over every occurrence in one stroke: a term in both the YES
  and NO boxes is highlighted in both, keeping the two boxes alike
  (rule 7.4). When a later `page` line brings the page back, it shows
  at full view with every term clicked so far faintly highlighted and
  ticked off, and then clicks its own. Without `focus`
  the page shows at full view, with those ticks.

```toml
[section.line.visual]
kind = "page"
source = "quick-reference"
highlight = ["Increases California's Rainy Day Fund", "during economic downturns"]
```

- `highlight`, on a `page` only: a non-empty list of phrases on the
  card, each matched case-sensitively like `focus`; every occurrence of
  each is highlighted, with a translucent yellow highlighter band laid
  behind the words (never the accent colour, and the same in the YES
  and NO boxes) that sweeps on left to right. Each phrase
  must occur in the card's text. A line has `focus` or `highlight`, not
  both.
- **Balance (rule 7.4):** across the whole script, the number of
  highlighted occurrences inside the YES box must equal the number
  inside the NO box; the check fails with both counts otherwise. Each
  phrase counts once for every time it occurs in each box, so a phrase
  the two boxes share (`"Rules for building state budget reserves"`)
  balances itself.
- **Timing:** the narration is timed per sentence only, so each phrase's
  sweep starts at its estimated spoken position in its line: if the
  phrase's words occur in the line's text (case-insensitive), at that
  character offset's fraction of the line's spoken duration (punctuation
  ignored); otherwise the line's phrases are spread evenly through it,
  in order: the k-th of n (counting from 0) at k/n of it. The
  occurrences of one phrase sweep on one after another, about 0.5 s
  each.
- Consecutive `page` lines in a section are one continuous page: no
  fade, no redraw and no return to full view between them; each line
  adds its highlights or its click. Highlights stay up as long as the
  page does; when the page comes back later they are gone (the ticks
  for clicked terms stay).

The `number` and `words` kinds of earlier versions only showed text;
the check fails a script that uses either, and says to use an
illustration or a chart instead.

Every visual but an illustration has a `source`, which must also be
among the line's `sources`. Everything a visual shows (titles, labels,
items) is held to the judgment-word check, like the narration; the
card's quoted text is the one exception (above).

### The measure template, version 2

Sections, in this order: `what`, any number of `background` sections
(zero or more, each with its own heading), `today`, `change`, `fiscal`,
the two sides, `vote`. Background sections tell the story behind the
contest (STANDARD.md section 6). Visuals may appear in any section. In
the sides (STANDARD.md rule 7.3), a chart, timeline, list or page only
when both sides have one of the same kind (a `list` also needing the
same number of items in all), and an illustration only when both sides
have the same number of them.

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
