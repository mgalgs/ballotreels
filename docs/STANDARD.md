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
     state's official fiscal statement (in California, the Legislative
     Analyst's Office's fiscal analysis; in Utah, the "Fiscal Effects" in
     the Voter Information Pamphlet), and the official arguments for and
     against as printed in the state's official voter guide; and, for
     background only (section 6) and for the budget total that gives a
     dollar figure its scale (rule 6.5), reports and
     published data from the state's nonpartisan fiscal offices (in
     California, the Legislative Analyst's Office and the Department of
     Finance);
   - where a state publishes no official voter guide at all: a
     **public university's nonpartisan ballot guide**, and only for what
     no official document states (plain-language explanation, and what
     supporters and opponents say). The video names the guide's
     publisher every time it relies on it ("the University of Arkansas
     Division of Agriculture's guide says…"), so a viewer never takes it
     for the state's own words. It is never a source for the ballot
     title, the measure's text, or a cost; those still come only from
     the official documents above;
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
5. A dollar figure about a government's money (its revenue, spending,
   costs, savings or borrowing) is stated with its scale: its share of
   the relevant budget, or that budget's total beside it. A bare large
   number reads as huge to one viewer and trivial to another, and which
   way it reads tilts the contest.
   - The total comes from a source in rule 1.2: the fiscal analysis
     where it states one, otherwise the state's nonpartisan fiscal
     offices.
   - The budget compared against is fixed, never chosen per script: the
     one the fiscal analysis itself compares the figure against; where
     it names none, the government's main operating budget (in
     California, the General Fund) for the matching period: a yearly
     figure against a year's spending, a two-year figure against the
     two-year budget.
   - Where the analysis states the comparison in its own words ("about
     one-quarter of 1 percent of the state's total General Fund
     budget"), the script uses those words. Otherwise the share is
     computed, and this is the one exception to rule 1.1's requirement
     that a source state every claim: one cited figure divided by
     another, rounded to a whole percent, with both sources cited; no
     projection, adjustment or other step. A range stays a range ("about
     2 to 6 percent of the state's General Fund spending"), and a share
     under 1 percent is said as "less than 1 percent of ...".
   - Exempt: a figure with no official total to compare against (one
     spread over an unstated number of years has none); an amount per
     person or household (an income threshold, a home price, a tax per
     person); and money not paid from or into a government's budget
     (bonds the analysis says homeowners repay, not the state).
   - The rule covers the narration and every number on screen except
     the card, which is quoted verbatim. A chart showing the figure may
     show its share too, with both sources named under it (rule 7.1).

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

## 8. Choice questions

Some questions ask voters to pick one of several options rather than
answer yes or no (Idaho's advisory question on a state gun). Such a
question has no for and against: its options take the place of the two
sides, and the rules of section 2 for sides become these. (This section
was added under version 2 without a new version: it governs only choice
questions, and no video of one was made before it.)

1. **Ballot order.** The options are listed, drawn and narrated in the
   order the ballot prints them, and in no other order.
2. **Verbatim labels.** Each option's letter and label are quoted
   exactly as the cited official source prints them, on the card and
   on the grid. The narration names each option as printed, and may
   leave out a part in parentheses (a calibre, a code) that reads badly
   aloud; the drawn label keeps it.
3. **Every option, equally.** The narration names every option, the
   same number of times, with the same treatment: no option gets a
   description, a reason, or more words than another. If the official
   guide describes each option, the script may say so, and describes
   none.
4. **Equal treatment on screen.** Every option is drawn on one sheet, a
   grid of equal cells: the same cell size, the same drawing size and
   treatment, the same label face and size, and the same drawing-on
   time for each. No option is highlighted, enlarged, coloured
   differently, ranked or set apart, on the grid or on the card.
5. **No ranking.** Nothing says or implies that one option is more
   popular, more fitting, more historic or more likely than another.

## 9. Naming people

Some measures have well-known authors and opponents: a governor who put
one on the ballot, a legislator who sponsored it. Leaving them out can
leave a viewer knowing less than the news would tell them. These rules
let a script name them without taking a side. (Added under version 2
without a new version: it permits naming and never requires it, so
every video made before it still meets the standard.)

1. **Named only from the record.** A person, organisation, law, court
   case or event is named only where an official record states its role
   in this measure: its filing with the election official (its
   proponents or sponsoring committee), the legislative record (sponsors,
   the roll-call vote, a governor's signature or veto), the official
   voter guide (the signers of each argument), or a statement by an
   officeholder on that office's official website. That last is a source
   kind for one fact only, that the officeholder holds a stated position
   on the measure; the claims inside the statement are not sources.
   Being in the news about a measure is never enough, for anyone.
2. **Role, nothing more.** A name comes with its role in the record:
   "Governor X, who signed the resolution placing it on the ballot". No
   motive, no description, no adjective; party only in rule 3.5's fixed
   form.
3. **Each side's most prominent, the same way.** Where a script names
   the most prominent supporter, it names the most prominent opponent in
   the same form of words, in the same kind of section, as many times.
   "Most prominent" is fixed, not chosen: an elected official acting in
   office, highest office first; then the official proponent or
   sponsoring committee; then the first signer of the official argument.
   Between officials of the same office, the one whose recorded role in
   this measure is larger comes first: a sponsor, then a signer of the
   official argument, then a recorded vote alone; a leadership post
   outside this measure counts for nothing.
4. **No one on the record, said plainly.** Where the record names no one
   on one side, the script may still name the other side's, and says
   that the record names no one on the other.
5. **Where names go.** In the background, as a fact of the record
   ("Governor X signed the resolution placing it on the ballot"), or in
   a side's own section ("Supporters, including Governor X, say..."); never
   in the opening line or the vote lines.

## Machine checks

The pipeline rejects a script or render that fails any of these. They
check the rules above that a machine can check; they do not replace a
human reading the video.

| Check | Rule |
|---|---|
| Every non-connective sentence cites a source id that exists in the contest's archived sources | 1.1, 1.4 |
| Every cited source is of an allowed kind | 1.2, 1.3 |
| A university ballot guide is cited only where the contest has no official argument, only in the explanation (background, today, change) and the sides, and only by a line that names its publisher | 1.2 |
| Same sections per candidate / per side, word counts within 5% | 2.1, 2.2, 2.4 |
| Candidate order matches the rule in 2.3 | 2.3 |
| No word from the judgment-word list in narrator text | 3.1 |
| Before narration (a script whose narration is missing or stale): no phrase the narration would speak afresh (an edited one, or the one right after it; a reused phrase already passed) uses a spelling the narration's transcript check mishears (`standard/speakability.txt`), so the narration can stay the script verbatim | none: a production check |
| Before narration: the two measure sides' estimated spoken durations (numbers, money and symbols said in full, timed from syllables, letters and pauses fitted to the committed narrations) within 1.1s of each other, so the narration will not need more than the airtime check's 2s of padding | 2.2 |
| Each measure side's on-screen time exactly equal, the shorter one padded with trailing silence (padding over 2s fails instead, as too big to be TTS noise) | 2.2, 4.1 |
| Each measure side's line quotes, as its `basis`, the passages of its cited official argument it distils, each verbatim in that source; required before narration (a script whose narration is missing or stale) | 3.3 |
| Every chart cites a source id that exists, of an allowed kind | 7.1 |
| No chart in a side section unless both sides have one | 7.3 |
| A choice question's options: letters in ballot order, each letter and label verbatim in the cited source, each spoken name the label with or without its parenthesised parts, the narration naming each once, in ballot order, on its own grid page, and every option as often as every other; no sides, no yes/no lines on its card | 8.1-8.4 |

Standard version: 2
