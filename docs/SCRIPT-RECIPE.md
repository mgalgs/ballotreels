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
- **Name the fiscal statement's author or publication** as the guide
  does ("The Legislative Analyst's Office says…" in California; "The
  Voter Information Pamphlet's analysis says…" in Utah, which names no
  office), never "experts" or "analysts".
- **State both the effect and the trade-off** wherever the analysis gives
  both (STANDARD rule 6.4). If one line says what the measure buys, another
  says what it costs.
- **Give every government dollar figure its scale** (rule 6.5), in the
  same line as the figure: "…$500 million to $600 million a year, about
  one-quarter of 1 percent of the state's General Fund budget." Use the
  analysis's own comparison when it gives one; otherwise divide the
  figure by the General Fund total for the same period, both cited
  ("about 2 to 6 percent of the state's General Fund spending"; "less
  than 1 percent of …" below 1). Per-person amounts, money the state
  neither pays nor receives, and figures with no matching total are
  exempt. If no archived source states the total, stop and ask for
  one; never use a remembered figure. STANDARD rule 1.2 allows a
  fiscal office's report for that total; a `fiscal` line cites it
  beside the fiscal analysis.
  Pay for the added words within the same neutral section, never from
  a side.
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

Two lines, one per vote, in the ballot's own words for the choices
("yes"/"no" in California, "for"/"against" in Utah), each saying what
that vote means as the official page says it, with a `page` visual that
highlights the phrase it quotes. Where the card has yes/no statements
(California), quote them: "A yes vote means …" and "A no vote means …",
each highlighted in its box. Where it has none (Utah), never invent
them: take the two meanings from the card's own sentences (the ballot
title or the summary), highlighting one phrase for each vote, so the two
lines stay parallel. Side headings use the same words ("Why some vote
for").

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

## Choice questions

A question that asks voters to pick one of several options (format:
SCRIPT-FORMAT.md's `[choices]`; rules: STANDARD.md section 8) has no
sides and no arguments. Its story is shorter: what it asks; any
background its official sources state (whether it is binding, what
would have to happen next); the choices; what the fiscal statement
says; how to vote. A shorter film is fine; padding is not.

- **The choices section** names every choice once, in ballot order, and
  nothing about any one of them: no description, no history, no
  nickname beyond what the ballot prints. Short connecting words
  ("Then …") are shared by all. If the guide describes each option,
  one line may say so.
- Name each choice as printed, leaving out a parenthesised calibre or
  code that reads badly aloud (`spoken`); the drawn label keeps it.
- Split the names across the section's lines so each is short to hear;
  with more than six choices, the lines of each grid page name only that
  page's choices.
- **Drawings**: one per choice, all with the same kind of subject (the
  option alone, plain, no people and no text). Ask for new ones in the
  contest's `illustrations-wanted.txt` (`name|subject`, one a line).
- **Vote line**: quote the ballot's own instruction ("Please choose only
  one answer"), highlighted on the card.
- Read it as someone who favours each choice in turn. If any would
  call a line unfair to theirs, rewrite it.

## Before it is done

- `python -m ballotreels check <contest-dir>` passes.
- Read the script aloud. Every sentence should make sense heard once,
  with no reading back.
- Read it as a supporter, then as an opponent. If either would call a line
  unfair, rewrite it.
