# The even-handedness standard

Even-handedness is the product. A ballotreels video that leans, even
slightly, is a defect of the same severity as one that misstates a fact.
This file is the standard every video must meet. Script generation is
built to satisfy it, and the checks in the pipeline enforce the parts a
machine can check. A video that fails any rule is not published.

The standard is versioned (see the bottom of this file). Every video
records the version it was made under, and a change to the standard
invalidates the cache for every video made under an older one.

## 1. Every claim has a source

1. Every factual sentence in a script cites at least one source by id.
   Sentences that only connect ("Here is what each side says.") are
   marked as connective and carry no claim.
2. A source is a **primary or official document**:
   - for a measure: the official title and summary, the full text, the
     official fiscal analysis (in California, the Legislative Analyst's
     Office), and the official arguments for and against as printed in
     the voter guide; and, for background only (section 6), reports and
     published data from the state's nonpartisan fiscal offices (in
     California, the Legislative Analyst's Office and the Department of
     Finance);
   - for a candidate: the candidate's own ballot designation and
     statement as filed with the election official, the candidate's own
     website or published statements, and public records (FEC filings,
     voting records, offices held).
3. Not sources: news articles, editorials, endorsements, ratings,
   polls, advocacy groups' analyses, and social media posts by anyone
   other than the candidate. These may be used to *find* a primary
   document, never cited in its place.
4. Every source is archived when it is used (a stored copy plus its URL
   and retrieval time), so a claim can be checked after the page changes.
5. The sources are shown with the video: a list on the video's page and
   a closing card in the video itself naming where the facts came from.

## 2. Equal structure and airtime

1. Every contest of a kind uses the same script template. A measure
   video has the same sections in the same order as every other measure
   video; a race video likewise.
2. Within a race, each candidate gets the same sections, the same word
   budget (within 5%), and the same on-screen treatment: same card
   layout, same type size, same time on screen.
3. Candidate order follows the order on the official ballot. Where the
   ballot order varies by district (California rotates it), use
   alphabetical order by last name and say so.
4. For a measure, the "yes" and "no" sections get the same word budget
   (within 5%), and the order of the two sections alternates by contest
   (by a stable hash of the contest id), so neither side always goes
   first.
5. A candidate with no filed statement or published positions is still
   shown, with the same card, and the script says plainly that no
   statement was filed. Their airtime is not given to anyone else.

## 3. Neutral language

1. No adjectives or adverbs of judgment in the narrator's own voice:
   no "bold", "extreme", "common-sense", "controversial", "radical",
   "sensible", "dangerous", "landmark", "sweeping", and so on. A
   checked-in word list (`standard/judgment-words.txt`) is enforced
   mechanically; it is a floor, not the whole rule.
2. Positions are attributed, never adopted: "Supporters argue the
   measure would lower costs", never "The measure would lower costs",
   unless the claim is the official fiscal analysis's, which is then
   attributed to that office by name.
3. Each side's arguments are stated in their strongest form, as the
   side itself states them, in a similar register for both sides.
4. No predictions, no recommendations, and no characterisation of a
   side's motives. The video never says how to vote, and never implies
   it.
5. Identical facts get identical wording across candidates: party
   labels, incumbency and office held are stated in one fixed form.

## 4. Neutral production

1. One visual template and one narration voice for every video in a
   contest. Colours never map to parties or to yes/no in a way that
   carries a connotation (no red/blue for parties, no green/red for
   yes/no).
2. No music cues, sound effects or visual effects that differ between
   sides.
3. No images of candidates in the pilot. If photos are added later,
   every candidate gets an official photo of the same crop and size, or
   none does.

## 5. Corrections

1. Every video page says how to report an error.
2. A confirmed error is fixed by regenerating the video, never by
   editing it by hand, and the page notes the correction and its date.

## 6. Explaining

A video explains what the contest is about before it says what anyone
thinks of it. It tells the story a voter needs: what problem or
situation the contest is about, how things work today and how they got
that way, what would change, and what it would cost. Plain language,
one idea per sentence, no legal terms a viewer has to already know.
The rules below keep that story neutral.

1. Background and context come from the official sources in rule 1.2:
   the fiscal analysis, and the nonpartisan fiscal offices' reports and
   data. They are limited to what those sources state as fact (how the
   budget works, what happened in past years, what the numbers are).
   An office's evaluations, recommendations and preferred options are
   not background, even when that office is nonpartisan.
2. A measure's purpose is stated as its authors' purpose ("The
   Legislature placed it on the ballot to..."), never in the narrator's
   voice as what the measure will achieve. What it would *do* is stated
   as the fiscal analysis states it.
3. A fact a side cites as part of its argument belongs to that side. It
   appears in that side's section, attributed to that side, and is not
   repeated, previewed or set up in a neutral section. Example: if
   supporters cite the Legislative Analyst's recommendation to save
   more, that recommendation is not mentioned in the background.
4. Background treats both outcomes alike. It does not dwell on the
   problem one side wants solved while passing over the cost the other
   side objects to; where the fiscal analysis states both an effect and
   its cost, the story states both.

## 7. Charts and visuals

1. Every number on screen comes from a cited source, and the source is
   named on screen, under the chart, for as long as the chart is shown.
2. Bar and area charts start at zero. No truncated or broken axes, no
   3D, no dual axes. Time runs left to right at an even scale.
3. Charts appear in neutral sections. A side's section shows only that
   side's own words, unless both sides get a chart of the same kind and
   size.
4. The options on the ballot get identical visual treatment. "Today"
   and "if it passes", or "yes" and "no", share one colour and weight;
   neither is highlighted with the accent colour, drawn larger, or
   animated differently.
5. A chart shows what its source shows. It does not extend a series,
   add a projection, or annotate a value with a judgment ("only",
   "record", "dangerously low").

## Machine checks

The pipeline rejects a script or render that fails any of these. They
check the rules above that a machine can check; they do not replace a
human reading the video.

| Check | Rule |
|---|---|
| Every non-connective sentence cites a source id that exists in the contest's archived sources | 1.1, 1.4 |
| Every cited source is of an allowed kind | 1.2, 1.3 |
| Same sections per candidate / per side, word counts within 5% | 2.1, 2.2, 2.4 |
| Candidate order matches the rule in 2.3 | 2.3 |
| No word from the judgment-word list in narrator text | 3.1 |
| Each candidate's or side's on-screen time within 5% | 2.2, 4.1 |
| Every chart cites a source id that exists, of an allowed kind | 7.1 |
| No chart in a side section unless both sides have one | 7.3 |

Standard version: 2
