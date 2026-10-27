# Writing a measure script

How to write a measure's `script.toml` (format: [SCRIPT-FORMAT.md](SCRIPT-FORMAT.md))
so it meets [the standard](STANDARD.md) and plays well as a 60-second video.
The reference script is `data/ca-2026-11-03/prop-2/script.toml`; read it
before writing another.

## Shape

- **About 60 seconds of narration**: roughly 120 to 140 words in all, in
  about six claims. Distil hard. A viewer remembers a few ideas, not a
  list of provisions; leave out anything a voter does not need to decide.
- **One claim per line.** Each line is one sentence that says one thing.
  The narration pauses between lines, so short lines let it breathe.
- **Build from one question.** Think of how a Vsauce episode builds an
  explanation from one simple question. Aim for that kind of structure,
  in our own plain, neutral voice, without tangents. For a measure, the
  question is usually "what problem is this about?", and each line follows
  from the one before: what the thing is, why it exists or matters, what
  it costs or trades off, how it works today, what the measure would
  change, what the official fiscal analysis says.
- **Sections** follow the template: `what`, then `background` sections as
  the story needs them, `today`, `change`, `fiscal`, the two sides, `vote`.

## Wording

- Plain words, short sentences, no legal terms a viewer has to know
  already. Say "the fund" or "the limit", not a code section.
- **No pronoun that reaches back across a sentence.** Each line is heard
  alone, a second after the last; name the thing again instead of "it".
- **No word with a misleading second meaning nearby.** For example, do not
  say "limit" for a fund's cap in a script that also talks about the state
  spending limit.
- **Name the fiscal office** ("The Legislative Analyst's Office says…"),
  never "experts" or "analysts".
- **State both the effect and the trade-off** wherever the analysis gives
  both (STANDARD rule 6.4). If one line says what the measure buys, another
  says what it costs.
- Purpose is the authors' purpose ("The Legislature placed it on the
  ballot to…"), never the narrator's claim (rule 6.2).

## Sides

- One line per side, attributed ("Supporters say…", "Opponents say…"),
  each the side's strongest point as the side itself states it in the
  official arguments.
- **Equal word counts** (the check allows 5%; aim for exact).
- Each side gets a `list` of **two items**, its two strongest points, in
  short form and about the same length as the other side's items.
- Nothing a side argues appears in a neutral section (rule 6.3).
- When one side filed no argument, say so plainly in that side's line;
  never fill the gap with the narrator's own words. The other side keeps
  its usual two-item list; the silent side's section sets `filed = false`
  and lists one item, "No argument against was submitted" (or "for").
  Leaving the lists out draws two empty boxes.

## Vote lines

Two lines, one per vote, each quoting the card's own words for what the
vote means: "A yes vote means …" and "A no vote means …", with a `page`
visual that highlights the quoted phrase in its box. The phrases come
from the official yes/no statements, so the two lines stay parallel.

## Visuals

- Open on the `page` card, highlighting the phrase that names the topic.
- A number belongs on a chart (`bars`, `share`, `series`) whose source
  states it; a concept with no data gets an `illustration`.
- Give most lines a visual; a section's visual stays up through its later
  lines.
- An illustration must exist in `film/illustrations/` before the check
  passes. A new one is added to `illustrations.toml` with a `subject`
  following the manifest's rules (objects and places, no people, no text),
  then generated with the manifest's style and approved by a person.

## Before it is done

- `python -m ballotreels check <contest-dir>` passes.
- Read the script aloud. Every sentence should make sense heard once,
  with no reading back.
- Read it as a supporter, then as an opponent. If either would call a line
  unfair, rewrite it.
