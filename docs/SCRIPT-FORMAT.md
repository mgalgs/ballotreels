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

`official-fiscal-analysis` is the state's official fiscal statement on
the measure, whoever writes it: in California, the Legislative Analyst's
Office's analysis; in Utah, the "Fiscal Effects" in the Voter
Information Pamphlet's Impartial Analysis. One archived file may back
several sources of different kinds (Utah prints the ballot title,
analysis, arguments and text in one pamphlet section).

`official-report` (a nonpartisan fiscal office's report or handout) and
`official-data` (a published data file from one) are background-only
(STANDARD.md rule 6.1): a line or chart may cite them only in a
`background` section. The one other use is the budget total behind a
scale (STANDARD.md rule 6.5): a line in the `fiscal` section may cite
one beside the `official-fiscal-analysis` that states the figure.

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

A line in a side section may also have a `basis`: the passages of the
side's official argument that the line distils, each quoted verbatim.

```toml
[[section.line]]
text = "Supporters say Montana grants artificial persons all the powers they have, so it can limit them."
sources = ["arguments"]
basis = ["Montana grants them every power they have.", "And Montana has reserved the authority to modify those"]
```

- `basis` is a list of one or more strings, each a sentence or a
  fragment of at least 6 words, and each must appear in the archived
  text of an `official-argument` source the line cites. It is compared
  as the card is (above), and looser still, since arguments are often
  PDFs: ligatures ("ﬁ") unfolded, curly quotes and straight ones alike,
  and hyphens and dashes ignored with the spaces around them, so a word
  hyphenated across a line break ("con- sents", "socialmedia") matches.
- Only a side's lines may have one.
- **Required until the script is narrated**: when the contest's narration
  is missing or stale (`narration.json` no longer matches the script),
  every non-connective line of a side that filed an argument must have a
  `basis`. A script narrated without one keeps passing; editing it makes
  its narration stale, and the edited script needs one.
- What it is for: SCRIPT-RECIPE.md, "Sides". The check makes the line
  traceable; whether the line says what its basis says is for the
  writer and the reviewer.
A line that states a computed share of a budget (STANDARD.md rule 6.5)
lists the source of the figure and the source of the total; when one
source states both, that one id is enough.

### The card: the measure's official page

A script may open on a drawn copy of the top of the measure's page in
the state's official voter guide, and come back to it to "click" the
terms on it (the `page` visual, below). The optional top-level `[card]`
table quotes that page:

```toml
[card]
source = "quick-reference"   # a source of the kind the state's card quotes
number = "2"                 # drawn under the badge word: "PROP 2"
title = "INCREASES STATE’S RAINY DAY FUND. LEGISLATIVE CONSTITUTIONAL AMENDMENT."
origin = "Put on the Ballot by the Legislature"
summary = "Increases California's Rainy Day Fund, ... Fiscal Impact: State budget reserves would be higher."
yes = "A YES vote on this measure means: ..."   # optional, with `no`
no = "A NO vote on this measure means: ..."
```

Utah's card quotes its pamphlet section instead, and has a `fiscal`
quote and no `yes`/`no` (its pamphlet prints no such lines):

```toml
[card]
source = "pamphlet"
number = "B"
title = "Shall the Utah Constitution be amended to require ...?"   # the ballot title
origin = "2025 Legislative General Session Senate Joint Resolution (S.J.R.) 2"
summary = "Constitutional Amendment B would increase ..."   # its "Effect of" paragraphs
fiscal = "Enactment of Constitutional Amendment B likely would not ..."   # optional
```

- `source`, `number`, `title`, `origin` and `summary` are required;
  `fiscal`, `yes` and `no` are optional, and `yes` and `no` come
  together or not at all. Each is a non-empty string. `source` must be
  in `sources.toml`, of the kind the state's card quotes (below).
- **Verbatim**: `title`, `origin`, `summary`, `fiscal`, `yes` and `no`
  must each appear in the archived source's text. A page is compared
  after stripping its markup (and the contents of its scripts and
  styles) and decoding entities; a PDF by its text as poppler's
  `pdftotext` extracts it (the check fails, saying so, where pdftotext is
  not installed). Either way whitespace is collapsed and whitespace
  before punctuation ignored (the page renders as `Fiscal Impact :
  State`). Quotes and case are compared as they are: the title is
  upper-case, with a curly apostrophe, on the page. A failure names the
  field.
- **The state's own words** come from its entry in
  `ballotreels/ballots.py`, one per state, never per measure; a measure
  in a state with no entry fails the check. The entry gives the guide's
  name (California's Official Voter Information Guide, Utah's Voter
  Information Pamphlet), the source kind its card quotes
  (`official-title-summary` for both), the fiscal statement's heading as
  printed (`Fiscal Impact:`, set in bold where the summary quotes it;
  `Fiscal Effects`, set in bold over the `fiscal` quote), the ballot's
  words for the two choices (`Yes`/`No`; `For`/`Against`), drawn as the
  ballot's options and the YES/NO box labels, and any abbreviation the
  guide prints on its badge (California's `PROP`).
- **The badge** is the measure's designation word in its contest title
  (`sources.toml`), the word just before its number ("Proposition 2:
  ...", "Constitutional Amendment A: ..."), upper-case or as the state
  abbreviates it: PROP 2, AMENDMENT A. A title with no such word fails.
- With no `yes` and `no`, the page draws no WHAT YOUR VOTE MEANS heading
  and no boxes, and leaves no room for them.
- The card is exempt from the judgment-word check: it is a verbatim
  official quote, not the narrator's voice (STANDARD.md rule 3.1).
  Everything else in the script keeps the check.
- The card has no supporters or opponents line and no arguments, on
  purpose: the arguments belong only to the side sections (rule 6.3),
  and the page's "Opponents: None submitted" sits beside a filed
  argument against.

### A choice question: `[choices]`

Most measures ask yes or no. A question that asks voters to pick one of
several options (Idaho's advisory question on a state gun: "Please
choose only one answer") opts in with a top-level `[choices]` table,
listing the options in ballot order (STANDARD.md section 8):

```toml
[choices]
source = "pamphlet"          # where the options are quoted from: the card's source

[[choices.choice]]
letter = "(a)"               # as printed; every choice has one, or none does
label = "Winchester Model 1894 (.30-30)"   # verbatim, drawn on the card and the grid
spoken = "Winchester Model 1894"           # optional: as narrated; defaults to the label
illustration = "winchester-model-1894"     # its drawing on the grid, from the library
```

- At least 2 choices. `source` must be in `sources.toml` and, with a
  card, be the card's own source.
- **Verbatim**: each choice's letter and label, joined by a space ("(a)
  Winchester Model 1894 (.30-30)"), must appear in the source's text,
  compared as the card is, except that a hyphen in the label may be
  missing from a PDF's text (pdftotext joins a word hyphenated across a
  line break: "bolt-" and "action" come out "boltaction"). Leave out the
  ballot's list punctuation (a trailing ";" or "or").
- **Letters** run on from the first of a series once stripped to their
  letters and digits: a, b, c ...; A, B, C ...; or 1, 2, 3 ...
- `spoken` is the label, or the label with any of its parenthesised
  parts left out (a calibre or a code that reads badly aloud).
- `illustration` is an entry in the illustration library whose file
  exists, as for an `illustration` visual. Give every choice the same
  kind of subject (a plain drawing of the option alone), so none is
  drawn differently (rule 8.4).
- **The card** has no `yes` or `no`: it lists the choices, letter and
  label, one a row in one face, under THE CHOICES, where a yes/no card
  has its boxes. A `focus` or `highlight` never marks a choice on it.
  Everything else on the card works as for any measure.
- **The narration** names each choice by its `spoken` name (or label):
  exactly once in the `choices` section, in ballot order, while the grid
  page that shows it is up; and, over the whole script, every choice as
  often as every other (in practice, once each). A choice's label is a
  verbatim quote, exempt from the judgment-word check like the card; the
  narration is not.
- The checks fail a script with `[choices]` and sides, or with the yes/no
  sections; see "the choice question" below for its sections.

A line may carry one visual: a chart, a timeline, a list, an
illustration, the page card, or a choice question's grid. The centre of the frame shows only
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
  counts. The exception is a side that submitted no argument (rule 2.5):
  its section sets `filed = false` and its list has the one item "No
  argument against was submitted" (or "for"), and the counts are not
  compared, so the other side's points show as submitted. Where the state publishes no
  official argument on either side (DC, Florida), both sections set
  `filed = false`, each listing the one item "No official argument for
  was published" (or "against"), and each side's line says so once. In the two side sections specifically, the list does not get
  its own page: both sides share one slide, "What each side says" (see
  "the measure template" below for how the two sides share it).
- `illustration`: a picture of the line's topic when there is no data
  to chart. `name` is an entry in the illustration library,
  `film/illustrations/illustrations.toml`, and its file must exist.
  Every entry is a pencil sketch made once with an image model in the
  manifest's one style, approved by a person and checked in; the
  library grows as new topics need pictures. No `title` and no
  `source`: an illustration carries no facts, and the line's own
  sources cover what is said. An optional `stamp`, a few words on one
  line (at most 24 characters), is written in pencil across the top of
  the stage once the drawing is down, so a muted viewer reads the slide
  at a glance: `stamp = "None reported"` where the guide gives no cost
  estimate. It is on-screen text, so the judgment-word list applies to
  it; no other kind of visual may have one.

```toml
[section.line.visual]
kind = "page"            # the card: the measure's official page
source = "quick-reference"   # must equal card.source, and be among the line's sources
focus = "Rainy Day Fund"     # optional: the term to click
```

```toml
[section.line.visual]
kind = "choices"         # one page of a choice question's grid
source = "pamphlet"      # the [choices] table's source
```

- `choices`: a page of the grid of the `[choices]`, allowed only in the
  `choices` section and only with a `[choices]` table; nothing but
  `kind` and `source`. Each option is a cell: its drawing over its letter
  and label. The grid is the smallest of 1x2, 1x3, 2x2 and 2x3 (columns x
  rows on the 9:16 frame: "1x2" is one column of two stacked cells; the
  16:9 frame turns it on its side) that holds the page's options: 2 take
  1x2, 3 take 1x3, 4 take 2x2, 5 or 6 take 2x3. More than 6 take
  ceil(n / 6) pages, split as evenly as possible in ballot order, the
  earlier pages taking any extra one (7 = 4 + 3, 8 = 4 + 4, 13 = 5 + 4 +
  4), each page on the smallest grid for its own count
  (`ballotreels.grid`). The k-th `choices` visual shows page k, so the
  `choices` section has exactly one per page, the first on its first
  line, and no other visual. Cells fill in reading order, left to right
  then top to bottom; a partly filled grid leaves its last cell empty.
  Every cell is the same size on every page, its drawing the same size,
  its label in the same face and size at the same place, and each draws
  on in the same time, as the narrator names it (its name's estimated
  spoken position in the page's lines, as a highlight's is timed). The
  source is named under the grid.
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
the sides (STANDARD.md rule 7.3), the only visual is one `list` per side,
and only when both sides have one with the same number of items in all:
both sides share one slide, whose two blocks hold each side's checklist
and nothing else, so a chart, timeline, page or illustration in a side
fails the check rather than going undrawn.

### The choice question, under the measure template, version 2

A script with a `[choices]` table keeps `template = "measure"` and
`template_version = 2` (so the cache key, and every yes/no script, are
unchanged) and follows these sections, in this order: `what`, any number
of `background` sections, `choices`, `fiscal`, `vote`. There are no
sides: no section has a `side`, and the choices take the sides' place
(STANDARD.md section 8). Visuals may appear in any section but
`choices`, which shows only the grid (above). The film draws the
`choices` section as any section: its heading, then the grid's pages.

### The measure template, version 1

Sections, in this order: `what`, `today`, `change`, `fiscal`, the two
sides, `vote`. A version 1 script fails the standard-version check
under Standard 2. The rest of this section applies to both versions. The sides are `yes` (with `side = "yes"`) and `no` (with
`side = "no"`), whatever the ballot calls them; their headings use the
ballot's own words ("Why some vote yes", "Why some vote for"), and the
check fails a side heading that says the other side's word or another
state's. Which side plays first is decided at render time by a
stable hash of the contest id (STANDARD.md rule 2.4): the SHA-256 of
the UTF-8 contest id, `yes` first when its first byte is even and `no`
first when it is odd (`ballotreels.side_order`). The script file always
lists `yes` then `no`. Their word counts must be within 5% of
each other; until the script is narrated (its narration missing or
stale), their estimated spoken durations must be within 1.1 s
(`ballotreels.spoken`, numbers said in full); and their time on screen is
made exactly equal: the shorter
side's narration gets trailing silence to match the longer (STANDARD.md
rule 2.2), which is why the rendered video can run a couple of seconds
longer than the raw narration. On screen, the two sides share one
slide, "What each side says" (fixed template text, not from the
script), that stays up through both sections: two equal pencilled
boxes, one per side in play order (top/bottom in the 9:16 format,
left/right in 16:9), filling the page between the heading and the
caption. Each box is labelled with its own section's heading and, if
the side has a `list`, ticks that list in on its own lines, in the same
type, row heights and spacing in both boxes; a side with none shows just
its label. When both lists cite the same source, one source line sits
under both boxes; otherwise each box carries its own.

## glance.toml

`data/<election>/glance.toml` holds the figures behind a state page's
"ballot at a glance" list, which the viewer can sort by the size of each
measure's official fiscal estimate. It is one file per election, beside
`contests.toml`, with one table per measure, keyed by the measure's
directory name:

```toml
[prop-1]
source = "title-summary"   # an id in that measure's sources.toml
quote = "Increased state cost of $500 million to $600 million annually for about 25 years to repay the housing bond."
amount = 600000000         # dollars: the largest dollar figure the quote prints
period = "per-year"
direction = "cost"

[prop-41]
source = "title-summary"
status = "not-determined"
quote = "Unknown net fiscal effect."
```

- `source` (required) is the official fiscal statement, or the official
  guide's fiscal section, the figure is quoted from: a source of kind
  `official-fiscal-analysis` or `official-title-summary`. Where none is
  printed, it is the guide that prints none.
- `quote` is verbatim from that source's archived text, compared as a
  side's `basis` is (above): whitespace, quotes, ligatures and
  hyphenation do not matter.
- `amount` is the largest absolute dollar figure the quote prints (a
  range sorts by its high end), as a whole number of dollars: "$2.7
  billion" is `2700000000`. Only a figure printed with a dollar sign
  counts; "tens of millions of dollars" is not one. The check fails an
  amount that is not the quote's largest figure.
- `period` (with `amount` only) is the figure's period as the quote
  states it: `per-year`, `one-time`, `over N years`, `every N years`
  (one recurring figure per N years, as Utah's "every two years"), or
  `unstated`.
- `status`, instead of `amount`, when the statement prints no dollar
  figure: `none-printed` (no figure, including no statement at all, when
  `quote` is left out), `not-determined` (the statement says the effect
  cannot be determined or is unknown) or `no-material-impact` (it says
  there is no fiscal effect, or none of note). Any status but
  `none-printed` needs its `quote`.
- `direction` (optional) is only as the quote states it: `cost`,
  `revenue-loss`, `revenue-gain`, `savings` or `mixed`. It is never
  inferred, and is left out where the quote does not say.

Revenue and cost are both size: the list sorts by `amount` alone. Once
an election has a `glance.toml`, `python -m ballotreels check` on any of
its contests also checks the file: every measure in `contests.toml` has
an entry, and every entry meets the rules above.
