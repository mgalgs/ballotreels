"""The measure video template, version 2: the sketchbook (STANDARD.md 2.1).

    python -m ballotreels render data/ca-2026-11-03/prop-2 --format all
    BALLOTREELS_CONTEST=data/ca-2026-11-03/prop-2 python film/measure.py sheet --format all

One template for every measure contest that follows docs/SCRIPT-FORMAT.md
(template 2); nothing about any one contest lives here. It reads the
contest named by BALLOTREELS_CONTEST (default: Prop 2, so the authoring
tools work with no setup) and its committed narration, and lays the film
out on the narration's clock (`ballotreels.storyboard`).

The look is the approved sketchbook mock (film/mocks/sketchbook.py):
graphite on a cream grid page, one orange coloured pencil for headings
only (never a value, rule 7.4), coloured pencil (sketch.PALETTE: ochre,
honey, teal, sage, brown; never red, rule 4.1) for every chart, figure,
timeline and list mark, over graphite outlines, Caveat for labels and
Patrick Hand for captions and notes, captions on a taped paper scrap.

The motion is calm. Each section is a page: its heading, written and
underlined, and a stage below it. A visual draws on once, in about a
second, with a pencil that is on the page only while something is being
drawn, and then holds still; it stays up through the lines after it until
a later line in the section brings its own (the old one fades out) or the
section ends (the whole page fades out, and the next heading draws on).
The pencil (or the highlighter, on the page card) leaves as soon as its
own mark is drawn: it never sits over a finished picture. While it draws,
a soft sound follows it (film/draw_sound.py): dry graphite for the
pencil, a softer felt-tip swish for the highlighter, well under the
narration; otherwise the film has no music and no other sound effect.
The stage shows
- the line's visual, if it has one: a chart, a timeline, a list (a
  side's own points, as a checklist, drawn like a timeline but with a
  check instead of a date) or a named figure, with "Source: ..." under
  it for as long as it is up (rule 7.1), or an illustration from the
  library (film/illustrations/), which wipes on rather than being drawn
  line by line, and cites nothing of its own;
- or the measure's official page, drawn from the script's [card], in the
  full-page view: no running title or heading (they fade out, and back in
  with the next visual), the page over the whole notebook page from the
  binding to the caption, at the largest type that fits, and the caption
  and footer at the page's bottom. The first `page` line draws it on, and
  one with a `focus` "clicks" a term: a highlighter sweeps over it, and the
  page holds still (PAGE_ZOOM_MAX); one with a `highlight` sweeps the same
  highlighter over each phrase as the narrator reaches it. Every mark on
  the page is that highlighter's: a translucent yellow (never the headings'
  orange) behind the words, made by a highlighter pen in place of the
  pencil. Consecutive `page` lines are one page that stays up, each adding
  its highlights or its click; the page comes back later at full view, its
  highlights gone and every term clicked so far faintly highlighted and
  ticked off;
- in the `what` and `vote` sections, before any visual, the ballot: the
  measure's title and its two options, drawn alike;
- otherwise nothing: an empty page under the heading.
The two side sections are the one exception to one-section-one-page: they
share a single slide, "What each side says" (sides_group), that stays up
through both of them with no redraw in between. Under the fixed heading,
two congruent cards (sides_plan: top/bottom in 9:16, left/right in
16:9) hold the sides in play order, each labelled with its own section's
heading and ticking its own `list` in on its own lines (side_block, the
same code for both, built from line positions, never from the side —
rules 2.2, 4.1, 7.4). The two sides also get exactly the same time on
screen: narration.side_pad adds silence to the shorter side's spoken
audio (both in the layout and in the audio actually played, below), so
neither section is shorter on the page than the other. The film closes
on a card listing every cited source (rule 1.5).
A quiet footer under the caption, on every frame, says where to report a
bias (rule 5.1). At its left end, while a picture is on the stage, a small
graphite ring counts down to the picture changing: full as it appears,
empty as it goes, with no numbers.

Time is in frames: one frame a beat, since cuts follow the narration, not
a music grid.
"""
import functools
import math
import os
import random
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _p in (REPO_ROOT, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cairo  # noqa: E402
import numpy as np  # noqa: E402

import videobuilder as vb  # noqa: E402
from videobuilder import Box, paths, text  # noqa: E402

import draw_sound as dsnd  # noqa: E402
import sketch as sp  # noqa: E402
from sketch import (BROWN, DRAW, GRAPHITE, HONEY, OCHRE, ORANGE, RESTING_ANGLE,  # noqa: E402
                    SAGE, TEAL, Hatch, Item, Stroke, fade_item, hatch_item,
                    stroke_item, text_item)

from ballotreels.ballots import badge, ballot_for  # noqa: E402
from ballotreels.contest import load_contest  # noqa: E402
from ballotreels.illustrations import load_library  # noqa: E402
from ballotreels.narration import padded_phrases, padded_spans  # noqa: E402
from ballotreels.narration import shift_track, side_pad  # noqa: E402
from ballotreels.storyboard import frame as to_frame  # noqa: E402
from ballotreels.storyboard import layout as lay_out  # noqa: E402

for _f in sorted((HERE / 'assets' / 'fonts').glob('*.[ot]tf')):
    text.register(_f)
HAND = 'Caveat'          # headings and chart labels: a quick, slanted hand
PRINT = 'Patrick Hand'   # captions and notes: a neater, rounder hand

FPS = 30
GRID = vb.Grid(fps=FPS, bpm=FPS * 60)  # one frame a beat

# ---- the contest ----
CONTEST_DIR = Path(os.environ.get(
    'BALLOTREELS_CONTEST', str(REPO_ROOT / 'data' / 'ca-2026-11-03' / 'prop-2')))
CONTEST = load_contest(CONTEST_DIR)
# the state's own words for its ballot and its guide (ballotreels.ballots)
BALLOT = ballot_for(CONTEST.division)
VOICE = vb.speech.load(CONTEST_DIR / 'narration.wav')
# the shorter side (STANDARD.md 2.2) gets silence at its end so both sides
# spend exactly the same time on screen; everything below follows the
# padded clock, same as the padded audio built for FILM.sounds further down
PAD = side_pad(CONTEST)
BOARD = lay_out(CONTEST, VOICE.seconds, FPS)
TRACK = shift_track(VOICE.track_at(0, FPS), PAD)
PHRASES = padded_phrases(VOICE.phrases, PAD)
VOICE_SECONDS = VOICE.seconds + (PAD.seconds if PAD else 0)
# each line's spoken span, (first frame, last frame), by (section label, index)
SPOKEN = {(s.section, s.index): (to_frame(s.start, FPS), to_frame(s.end, FPS)) for s in padded_spans(CONTEST)}

PAPER_SCRAP = '#fbf7ec'
TAPE = (0.88, 0.82, 0.62, 0.62)

FADE = 12          # frames for a page, or a visual, to fade out (0.4 s)
DRAW_ON = 36       # frames a visual takes to draw on, at most (1.2 s)
BRIDGE = 6         # frames of gap the pencil crosses between two marks
PENCIL_FADE = 5    # frames for the pencil to fade in or out
WRITE_PX = 1500    # px of lettering a second

# Coloured-pencil assignments (sketch.PALETTE): one fixed colour per kind of
# mark, so every bar, segment, timeline entry and check is the same colour
# as every other of its kind (rule 7.4) and the same on both sides (rule
# 4.2). The two lines of the steady-spending figure differ, since neither
# is a ballot option. Text and outlines stay GRAPHITE throughout.
BARS_COLOUR = OCHRE
SHARE_COLOUR = SAGE
SERIES_COLOUR = TEAL
SPENDING_COLOUR = TEAL
REVENUE_COLOUR = BROWN
FUND_CANOPY_COLOUR = TEAL
FUND_COIN_COLOUR = HONEY
TIMELINE_COLOUR = BROWN
LIST_COLOUR = SAGE


def seed_of(*parts):
    """A stable seed from strings and numbers, so every frame, and every
    render, draws the same wobble."""
    return zlib.crc32('/'.join(map(str, parts)).encode())


def font(size, weight=400, family=HAND, **kw):
    return vb.Font(family, size, weight=weight, **kw)


def draw_budget(f0, f1):
    """Frames a visual starting at f0, up until f1, has to draw on in."""
    return min(DRAW_ON, (f1 - f0) * 0.8)


def write_frames(px):
    return max(4, px / WRITE_PX * FPS)


def number(v):
    """A value as printed: no trailing .0, at most two decimals."""
    v = float(v)
    if v.is_integer():
        return f'{int(v):,}'
    return f'{v:,.2f}'.rstrip('0').rstrip('.')


def with_unit(v, unit):
    """A value label, always with its unit (rule 7.2): '20%', '5 billion'."""
    unit = unit or ''
    if unit and unit[0].isalpha():
        return f'{number(v)} {unit}'
    return f'{number(v)}{unit}'


def short_name():
    """The measure's name as a ballot shows it: the title up to its colon."""
    return CONTEST.title.split(':', 1)[0].strip()


# ---- one layout table per format ----
def layout_9x16():
    return dict(
        W=1080, H=1920, u=1.0,
        safe=Box(70, 200, 940, 1340),
        # the running title's band: from under the binding's holes down to
        # the heading, which the title fills (header_fit)
        header=Box(70, 120, 940, 164),
        heading=Box(70, 292, 940, 118),
        # the stage runs down to just above the caption, which sits at the
        # page's bottom in every view, as in the full-page view
        stage=Box(70, 430, 940, 1166),
        scrap=Box(78, 1632, 924, 196),
        header_font=font(52, family=PRINT),  # at most: header_fit shrinks it to fit
        heading_font=font(86, 700),
        # a chart's lettering, sized to read on a phone: its title, its
        # category and line labels, its values, and its axis values
        chart_title_font=font(64, 700),
        chart_label_font=font(56, 600),
        value_font=font(64, 700),
        axis_font=font(44, family=PRINT),
        label_font=font(46, 600),
        note_font=font(34, family=PRINT),
        ballot_title_font=font(52, family=PRINT),
        option_font=font(84, 700),
        timeline_font=font(46, family=PRINT),
        caption_font=font(58, family=PRINT),
        caption_lines=2,
        sources_font=font(60, family=PRINT),  # at most: the sides slide's items' largest
        footer=Box(70, 1856, 940, 40),
        footer_font=font(30, family=PRINT),
        # the full-page view, while the official page is up: no running
        # title or heading, the page from under the binding down to the
        # caption, the caption and the footer at the bottom of the page
        page_stage=Box(24, 136, 1032, 1468),
        page_scrap=Box(78, 1632, 924, 196),
        page_footer=Box(70, 1856, 940, 40),
        # the countdown ring: (centre x, centre y, radius), at the footer
        # line's left end, in each view
        ring=(100, 1876, 22),
        page_ring=(100, 1876, 22),
    )


def layout_16x9():
    return dict(
        W=1920, H=1080, u=0.9,
        safe=Box(120, 124, 1680, 906),
        header=Box(120, 116, 1680, 48),
        heading=Box(120, 166, 1680, 96),
        stage=Box(150, 276, 1620, 540),
        scrap=Box(250, 842, 1420, 176),
        header_font=font(44, family=PRINT),
        heading_font=font(74, 700),
        chart_title_font=font(57, 700),
        chart_label_font=font(51, 600),
        value_font=font(57, 700),
        axis_font=font(40, family=PRINT),
        label_font=font(42, 600),
        note_font=font(31, family=PRINT),
        ballot_title_font=font(42, family=PRINT),
        option_font=font(64, 700),
        timeline_font=font(40, family=PRINT),
        caption_font=font(54, family=PRINT),
        caption_lines=2,
        sources_font=font(52, family=PRINT),
        footer=Box(250, 1034, 1420, 32),
        footer_font=font(25, family=PRINT),
        page_stage=Box(24, 128, 1872, 686),
        page_scrap=Box(250, 842, 1420, 176),
        page_footer=Box(250, 1034, 1420, 32),
        ring=(190, 1040, 20),
        page_ring=(190, 1040, 20),
    )


LAYOUTS = {'9x16': layout_9x16(), '16x9': layout_16x9()}


# ---- small drawing helpers ----
def box_pts(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def write_lines(f0, lines, fnt, x, y, align='left', width=None, ink=GRAPHITE, alpha=1.0, speed=1.0):
    """Lettering written line after line from frame f0. `x`/`width`: the
    block's left edge and width (lines aligned within it). Returns (items,
    end frame, Box drawn)."""
    items = []
    lh = text.line_height(fnt)
    f = f0
    widest = 0
    for i, ln in enumerate(lines):
        w = text.measure(ln, fnt)
        widest = max(widest, w)
        width_ = width if width is not None else w
        ax = {'left': x, 'center': x + width_ / 2, 'right': x + width_}[align]
        d = write_frames(w) / speed
        items.append(text_item(f, f + d, ln, fnt, ax, y + i * lh, ink, alpha, align=align))
        f += d
    bw = width if width is not None else widest
    return items, f, Box(x, y, bw, lh * len(lines))


def scaled(items, f0, budget):
    """Squeeze a run of items, laid out from f0, into `budget` frames."""
    if not items:
        return items
    end = max(it.f1 for it in items)
    span = end - f0
    if span <= budget:
        return items
    k = budget / span
    for it in items:
        it.f0 = f0 + (it.f0 - f0) * k
        it.f1 = max(it.f0 + 1, f0 + (it.f1 - f0) * k)
    return items


def paper(cx, cy, w, h, angle, dog=0, tape=True):
    """A sheet of paper laid on the page: its outline points (in its own
    rotated space) and a draw function for the paper, shadow and tape."""
    x0, y0 = -w / 2, -h / 2
    if dog:
        pts = [(x0, y0), (x0 + w - dog, y0), (x0 + w, y0 + dog), (x0 + w, y0 + h), (x0, y0 + h)]
    else:
        pts = box_pts(x0, y0, w, h)

    def draw(cv):
        ctx = cv.ctx
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(angle)
        cv.shape_shadow(pts, dx=5, dy=9, blur=16, color=(60, 40, 20, 0.2))
        paths.draw(cv, pts, PAPER_SCRAP, fill=True)
        if tape:
            for tx, ty, a in ((x0 + w * 0.5, y0 - 4, 0.04),):
                ctx.save()
                ctx.translate(tx, ty)
                ctx.rotate(a)
                ctx.rectangle(-60, -17, 120, 34)
                ctx.set_source_rgba(*TAPE)
                ctx.fill()
                ctx.restore()
        ctx.restore()
    return pts, draw


class Mark:
    """A named box for the checks, drawn from frame `f0` while its layer is
    not being rubbed out."""

    def __init__(self, name, box, f0=0):
        self.name, self.box, self.f0 = name, box, f0


# ---- the page heading ----
def heading_items(sec_beat, L, f0):
    return heading_text_items(sec_beat.section.heading, L, f0)


def heading_text_items(words, L, f0):
    hb = L['heading']
    fnt = L['heading_font']
    while True:
        lines = text.wrap(words, fnt, hb.w, balance=True)
        if len(lines) * text.line_height(fnt) <= hb.h - 14 or fnt.size < 40:
            break
        fnt = font(fnt.size * 0.92, 700)
    lh = text.line_height(fnt)
    y = hb.y + (hb.h - 14 - lh * len(lines)) / 2
    items, f, drawn = write_lines(f0, lines, fnt, hb.x, y, align='center', width=hb.w, speed=1.2)
    w = max(text.measure(ln, fnt) for ln in lines)
    uy = drawn.bottom + 2
    under = Stroke(sp.catmull([(hb.cx - w / 2 - 6, uy + 2), (hb.cx, uy - 2), (hb.cx + w / 2 + 10, uy + 3)],
                              per=10), seed_of('underline'), passes=2, width=5 * L['u'])
    items.append(stroke_item(f + 1, f + 9, under, ORANGE))
    return items, f + 9, Box(hb.cx - w / 2 - 10, drawn.y, w + 24, uy + 8 - drawn.y)


# ---- the stage: the ballot (the `what` and `vote` sections) ----
def ballot_run(lines, L, first_f):
    """The measure's ballot entry, drawn during the run's first line: its
    title, and its two options drawn alike, neither marked."""
    stage = L['stage']
    u = L['u']
    tf = L['ballot_title_font']
    of = L['option_font']
    w = min(stage.w * 0.92, 900 * u)
    pad = 46 * u
    while True:
        tl = text.wrap(CONTEST.title, tf, w - 2 * pad, balance=True)
        if len(tl) <= 4 or tf.size < 26:
            break
        tf = font(tf.size * 0.92, family=PRINT)
    title_h = text.line_height(tf) * len(tl)
    row_h = text.line_height(of) * 1.3
    h = min(stage.h, pad + title_h + 40 * u + 2 * row_h + pad * 0.6)
    cx, cy = stage.cx, stage.cy
    angle = -0.012
    at = (cx, cy, angle)
    pts, draw_paper = paper(cx, cy, w, h, angle)
    f = first_f
    budget0 = draw_budget(first_f, lines[-1].end)
    items = [fade_item(f, f + 6, draw_paper)]
    outline = Stroke(pts, seed_of('ballot'), passes=2, width=3.2 * u, closed=True, overshoot=0, alpha=0.75)
    items.append(stroke_item(f + 3, f + 14, outline, at=at))
    f += 14
    ti, f, _ = write_lines(f, tl, tf, -w / 2 + pad, -h / 2 + pad * 0.8)
    for it in ti:
        it.at = at
    items += ti
    f = max(it.f1 for it in items) + 2
    opt_items = []
    f1 = f
    ry = -h / 2 + pad * 0.8 + title_h + 22 * u
    rule = Stroke([(-w / 2 + pad, ry), (w / 2 - pad, ry)], seed_of('ballot rule'), passes=2, width=2.6 * u)
    opt_items.append(stroke_item(f1, f1 + 6, rule, at=at))
    f1 += 6
    # The two options, in the ballot's own words, drawn alike: same oval,
    # same lettering, same timing.
    for i, word in enumerate(BALLOT.choices):
        y = ry + 18 * u + row_h * (i + 0.5)
        ox = -w / 2 + pad + 60 * u
        oval = Stroke(sp.ellipse(ox, y, 46 * u, 26 * u, n=40), seed_of('oval'), passes=2, width=3.4 * u,
                      closed=True, overshoot=0)
        opt_items.append(stroke_item(f1, f1 + 10, oval, at=at))
        li, f1, _ = write_lines(f1 + 10, [word], of, ox + 80 * u, y - text.line_height(of) * 0.55)
        for it in li:
            it.at = at
        opt_items += li
        f1 += 4
    items = scaled(items + opt_items, first_f, budget0)
    bb = _rot_bbox(cx, cy, w, h, angle)
    return items, [Mark('ballot', bb)]


def _rot_bbox(cx, cy, w, h, a):
    r = abs(a)
    bw = w * math.cos(r) + h * math.sin(r)
    bh = h * math.cos(r) + w * math.sin(r)
    return Box(cx - bw / 2, cy - bh / 2, bw, bh)


# ---- the stage: charts ----
def source_note(chart, L, f0, stage=None):
    """'Source: ...' along the stage's bottom, on the page from the visual's
    first frame to its last (rule 7.1): (item, box). `stage` overrides
    L['stage'], for a visual confined to less than the whole stage (the
    sides slide's two blocks)."""
    stage = stage if stage is not None else L['stage']
    nf = L['note_font']
    words = f'Source: {chart.source.short_credit}'
    slines = text.wrap(words, nf, stage.w, balance=True)
    sh = text.line_height(nf) * len(slines)
    sy = stage.bottom - sh

    def draw_source(cv, p):
        sp.pencil_text(cv, slines, nf, stage.x, sy, GRAPHITE, 0.85, align='center', width=stage.w)
    return Item(f0 - 1, f0, draw_source, None, ease=vb.linear), Box(stage.x, sy, stage.w, sh)


def chart_frame(chart, L, f0):
    """The title above a chart and its source line below: (items, plot box,
    title box, source box). The source line is on the page from the chart's
    first frame to its last (rule 7.1)."""
    stage = L['stage']
    u = L['u']
    tf = L['chart_title_font']
    lines = text.wrap(chart.visual.title, tf, stage.w, balance=True)
    if len(lines) > 2:
        tf = font(tf.size * 0.85, 700)
        lines = text.wrap(chart.visual.title, tf, stage.w, balance=True)
    items, f, tbox = write_lines(f0 + 1, lines, tf, stage.x, stage.y, align='center', width=stage.w)
    src, sbox = source_note(chart, L, f0)
    items.append(src)
    sy = sbox.y
    plot = Box(stage.x, tbox.bottom + 26 * u, stage.w, sy - 22 * u - (tbox.bottom + 26 * u))
    return items, f, plot, tbox, sbox


class GrowBar:
    """A bar that grows up from the baseline, its hatching revealed with it:
    a coloured-pencil fill (`colour`) over a graphite outline."""

    def __init__(self, x, base, w, h, seed, u, colour=GRAPHITE):
        self.x, self.base, self.w, self.h, self.colour = x, base, w, h, colour
        top = base - h
        self.left = Stroke([(x, base), (x, top)], seed, passes=3, width=4.2 * u, overshoot=4)
        self.right = Stroke([(x + w, base), (x + w, top)], seed + 1, passes=3, width=4.2 * u, overshoot=4)
        self.top = Stroke([(x - 4, 0), (x + w + 6, 0)], seed + 2, passes=3, width=4.2 * u)
        self.fill = Hatch(box_pts(x, top, w, h), seed + 3, angle=52, spacing=13 * u, cross=True, alpha=0.65)

    def draw(self, cv, p):
        h = self.h * p
        if h <= 0:
            return
        top = self.base - h
        with cv.clip(self.x - 40, top - 6, self.w + 80, h + 30):
            self.fill.draw(cv, 1.0, self.colour, 0.85)
            self.left.draw(cv, 1.0)
            self.right.draw(cv, 1.0)
        ctx = cv.ctx
        ctx.save()
        ctx.translate(0, top)
        self.top.draw(cv, 1.0)
        ctx.restore()

    def head(self, p):
        return (self.x + self.w * 0.55, self.base - self.h * p)


def bars_chart(chart, L, f0, f1):
    v = chart.visual
    u = L['u']
    items, f, plot, tbox, sbox = chart_frame(chart, L, f0)
    lf, vf, af = L['chart_label_font'], L['value_font'], L['axis_font']
    n = len(v.values)
    vmax = max(max(v.values), 1e-9)
    zero = with_unit(0, v.unit)
    axis_w = max(120 * u, text.measure(zero, af) + 60 * u)
    slot = (plot.w - axis_w) / n
    bw = min(slot * 0.55, 250 * u)
    # one font for every label (rule 7.4), smaller only if a word would
    # not fit its slot
    while True:
        lab_lines = [text.wrap(str(lb), lf, slot - 16 * u, balance=True) for lb in v.labels]
        if max(text.measure(ln, lf) for ls in lab_lines for ln in ls) <= slot - 16 * u or lf.size < 22:
            break
        lf = font(lf.size * 0.94, 600)
    lab_h = max(len(ls) for ls in lab_lines) * text.line_height(lf)
    base = plot.bottom - lab_h - 14 * u
    top = plot.y + text.line_height(vf) + 8 * u
    scale = (base - top) / vmax
    x0 = plot.x + axis_w
    axis = Stroke([(x0 - 30 * u, base), (plot.right, base)], seed_of('axis'), passes=3, width=4.2 * u)
    items.append(stroke_item(f, f + 12, axis))
    items.append(text_item(f + 8, f + 12, zero, af, x0 - 40 * u, base - text.line_height(af) * 0.55,
                           alpha=0.8, align='right', pencil=False))
    f += 14
    grow = 24
    # Every bar the same: same ink, hatching, weight, growth and timing (rule 7.4).
    for i, (val, ls) in enumerate(zip(v.values, lab_lines)):
        cx = x0 + slot * (i + 0.5)
        li, f, _ = write_lines(f, ls, lf, cx - slot / 2, base + 10 * u, align='center', width=slot)
        items += li
        bar = GrowBar(cx - bw / 2, base, bw, val * scale, seed_of('bar', i), u, colour=BARS_COLOUR)
        items.append(Item(f + 2, f + 2 + grow, bar.draw, bar.head, ink=BARS_COLOUR))
        f += 2 + grow
        vi, f, _ = write_lines(f + 2, [with_unit(val, v.unit)], vf, cx - slot / 2,
                               base - val * scale - text.line_height(vf) - 4 * u, align='center', width=slot)
        items += vi
        f += 6
    items = scaled(items, f0, draw_budget(f0, f1))
    return items, [Mark('chart', Box(plot.x, tbox.y, plot.w, plot.bottom - tbox.y)), Mark('chart source', sbox)]


# ---- the stage: a timeline, an illustration ----
# An illustration's own paper is levelled away: tones at or above PAPER_LEVEL
# of the paper's local brightness turn to nothing, INK_LEVEL and darker to
# full graphite. The outer EDGE_FADE of the image (as fractions of its
# sides) fades out, so a sheet's edge or a stray mark there never shows.
PAPER_LEVEL = 0.9
INK_LEVEL = 0.25
EDGE_FADE = (0.025, 0.06)
WIPE = 30          # frames an illustration takes to wipe on (1 s)


@functools.lru_cache(maxsize=16)
def illustration_ink(name):
    """Illustration `name` as ink alone, its own colour kept: (a cairo
    surface to lay on the page with OPERATOR_MULTIPLY, cropped to the
    drawing; and its pixel buffer). Each channel's paper is levelled to
    nothing as a graphite file's grey always was, giving the factor
    `keep` (1 on paper, 0 at INK_LEVEL and darker) the page's channel is
    multiplied by, so the strokes look drawn on the page in colour. The
    surface has alpha A = 1 - min(keep) and premultiplied colour
    keep - (1 - A): multiplied onto an opaque page that gives page * keep.
    For a graphite file (R = G = B) the colour is 0: black ink at the
    darkness it always had, so it renders exactly as before."""
    from PIL import Image, ImageFilter
    im = Image.open(load_library()[name].path).convert('RGB')
    rgb = np.asarray(im, np.float32) / 255
    # the paper's tone at each point and in each channel: the lightest nearby, smoothed
    small = im.resize((max(1, im.width // 8), max(1, im.height // 8)), Image.BILINEAR)
    paper_ = small.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6))
    paper_ = np.asarray(paper_.resize(im.size, Image.BILINEAR), np.float32) / 255
    flat = np.clip(rgb / np.maximum(paper_, 0.3), 0, 1)
    dark = 1 - np.clip((flat - INK_LEVEL) / (PAPER_LEVEL - INK_LEVEL), 0, 1)  # per channel

    def ramp(n):
        t = np.minimum(np.arange(n), np.arange(n)[::-1]) / n
        return np.clip((t - EDGE_FADE[0]) / (EDGE_FADE[1] - EDGE_FADE[0]), 0, 1)
    dark *= (ramp(dark.shape[0])[:, None] * ramp(dark.shape[1])[None, :])[..., None]
    alpha = dark.max(axis=2)
    ys, xs = np.nonzero(alpha > 0.06)
    if len(xs):
        pad = 8
        box = (max(0, ys.min() - pad), ys.max() + pad + 1, max(0, xs.min() - pad), xs.max() + pad + 1)
        alpha = alpha[box[0]:box[1], box[2]:box[3]]
        dark = dark[box[0]:box[1], box[2]:box[3]]
    h, w = alpha.shape
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
    px = np.zeros((h, stride // 4, 4), np.uint8)
    premult = alpha[..., None] - dark  # in [0, alpha]: 0 (black) wherever a channel is darkest
    px[:, :w, 0] = np.round(premult[..., 2] * 255).astype(np.uint8)  # cairo's byte order is BGRA
    px[:, :w, 1] = np.round(premult[..., 1] * 255).astype(np.uint8)
    px[:, :w, 2] = np.round(premult[..., 0] * 255).astype(np.uint8)
    px[:, :w, 3] = np.round(alpha * 255).astype(np.uint8)
    data = bytearray(px.tobytes())
    surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, stride)
    return surf, data  # cairo borrows the buffer: keep it alive with the surface


def illustration_visual(chart, lines, L, f0, f1):
    """A pencil illustration from the library, centred on the stage as large
    as it fits, wiped on top to bottom with a soft edge (the pencil riding
    the edge) and then held still. It cites nothing of its own: the line
    does."""
    stage = L['stage']
    u = L['u']
    surf, _ = illustration_ink(chart.visual.name)
    iw, ih = surf.get_width(), surf.get_height()
    room_w, room_h = stage.w * 0.96, stage.h - 40 * u
    k = min(room_w / iw, room_h / ih)
    w, h = iw * k, ih * k
    x, y = stage.cx - w / 2, stage.cy - h / 2
    feather = 0.12 * ih  # the wipe's soft edge, in the image's pixels

    def draw(cv, p):
        ctx = cv.ctx
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(k, k)
        ctx.set_operator(cairo.OPERATOR_MULTIPLY)
        ctx.set_source_surface(surf, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_GOOD)
        if p >= 1:
            ctx.paint()
        else:
            edge = p * (ih + feather)
            g = cairo.LinearGradient(0, edge - feather, 0, edge)
            g.add_color_stop_rgba(0, 0, 0, 0, 1)
            g.add_color_stop_rgba(1, 0, 0, 0, 0)
            ctx.mask(g)
        ctx.restore()

    def head(p):
        # back and forth along the wipe's edge, as if shading it in
        sweep = 0.5 - 0.42 * math.cos(p * math.pi * 7)
        return (x + w * (0.06 + 0.88 * sweep), y + (p * (ih + feather) - feather * 0.5) * k)

    d = min(WIPE, max(8, (f1 - f0) * 0.8))
    items = [Item(f0, f0 + d, draw, head, ease=DRAW)]
    return items, [Mark('chart', Box(x, y, w, h))]


def timeline_reveals(n, lines, f0):
    """The frame each of a timeline's `n` entries starts drawing on: one per
    line from the first, the rest together with the last line, a moment
    apart."""
    out = []
    for i in range(n):
        if i == 0:
            out.append(f0)
        elif i < len(lines):
            out.append(max(out[-1] + 6, lines[i].start + 3))
        else:
            out.append(out[-1] + 18)
    return out


def timeline_visual(chart, lines, L, f0, f1):
    """Dated entries in a column down a spine, top to bottom, each drawn on
    with its line (docs/SCRIPT-FORMAT.md), and the source along the bottom."""
    v = chart.visual
    stage = L['stage']
    u = L['u']
    src, sbox = source_note(chart, L, f0)
    df, itf = L['label_font'], L['timeline_font']
    n = len(v.labels)
    spine_x = stage.x + 50 * u
    tx = spine_x + 50 * u
    tw = stage.right - tx
    while True:
        blocks = [(text.wrap(d, df, tw, balance=True), text.wrap(it, itf, tw, balance=True))
                  for d, it in zip(v.labels, v.items)]
        heights = [len(a) * text.line_height(df) + len(b) * text.line_height(itf) for a, b in blocks]
        room = sbox.y - 40 * u - stage.y
        if sum(heights) + 40 * u * (n - 1) <= room or itf.size < 26:
            break
        df, itf = font(df.size * 0.92, 600), font(itf.size * 0.92, family=PRINT)
    gap = max(40 * u, min(110 * u, (room - sum(heights)) / max(1, n - 1)))
    # centre the column on the stage
    widest = max(max(text.measure(ln, df) for ln in a) for a, _ in blocks)
    widest = max(widest, max(text.measure(ln, itf) for _, b in blocks for ln in b))
    shift = max(0, (stage.w - (tx - stage.x) - widest) / 2 - 20 * u)
    spine_x, tx = spine_x + shift, tx + shift
    y = stage.y + max(0, (room - sum(heights) - gap * (n - 1)) / 2)
    starts = timeline_reveals(n, lines, f0)
    items = [src]
    prev_dot = None
    top = y
    for i, ((dl, il), h, s0) in enumerate(zip(blocks, heights, starts)):
        dot_y = y + text.line_height(df) * 0.55
        entry = []
        f = s0
        if prev_dot is not None:
            spine = Stroke([(spine_x, prev_dot + 14 * u), (spine_x, dot_y - 14 * u)], seed_of('spine', i),
                           passes=2, width=3.4 * u, overshoot=0)
            entry.append(stroke_item(f, f + 8, spine, ink=TIMELINE_COLOUR))
            f += 8
        dot = Stroke(sp.ellipse(spine_x, dot_y, 10 * u, 10 * u, n=20), seed_of('tdot'), passes=2,
                     width=4 * u, closed=True, overshoot=0)
        entry.append(stroke_item(f, f + 5, dot, ink=TIMELINE_COLOUR))
        di, f, _ = write_lines(f + 5, dl, df, tx, y)
        ii, f, _ = write_lines(f + 2, il, itf, tx, y + len(dl) * text.line_height(df))
        entry += di + ii
        nxt = starts[i + 1] if i + 1 < n else f1
        items += scaled(entry, s0, draw_budget(s0, nxt))
        prev_dot = dot_y
        y += h + gap
    box = Box(spine_x - 14 * u, top, stage.right - spine_x + 14 * u, y - gap - top)
    return items, [Mark('chart', box), Mark('chart source', sbox)]


def check_mark_pts(cx, cy, s):
    """A hand-drawn check mark centred near (cx, cy), `s` px across: a short
    downstroke then a longer upstroke, one polyline with a corner at its
    low point."""
    return [(cx - s * 0.62, cy - s * 0.04), (cx - s * 0.14, cy + s * 0.46), (cx + s * 0.7, cy - s * 0.52)]


LIST_MAX_LINES = 2  # no item on the sides slide may take more lines than this


def list_wrap(item, fnt, width):
    """A sides-slide item's lines: filled out to `width` from the first
    line, so the text runs to the card's right edge. A lone word left on
    the last line takes the word before it with it, keeping the first line
    as full as it can be; balancing would leave it half empty."""
    lines = text.wrap(item, fnt, width)
    if len(lines) == 2 and ' ' not in lines[-1].strip():
        words = item.split()
        if len(words) >= 3:
            return [' '.join(words[:-2]), ' '.join(words[-2:])]
    if len(lines) > 2 and ' ' not in lines[-1].strip():
        return text.wrap(item, fnt, width, balance=True)
    return lines


def list_rows(every, L, width, fits, size):
    """The rows of one or more checklists laid out alike (rule 7.4): the
    largest item font (from `size` down) at which every item takes at most
    LIST_MAX_LINES lines and `fits(rows_h, gap, font)`. Rows are packed at
    their least gap here, half a line of the item font; the caller may
    widen it. Returns a dict: the font, each row's height (the tallest of
    that row across `every`), the gap, the rows' total height, and the
    check column's and text's offsets from the left edge (the checks at
    the edge, the text filling the rest of `width`: list_wrap)."""
    u = L['u']
    check = 40 * u
    tw = width - check - 30 * u
    itf = font(size, family=PRINT)
    n = max((len(its) for its in every), default=0)
    while True:
        wrapped = [[list_wrap(it, itf, tw) for it in its] for its in every]
        heights = [max(len(w[i]) for w in wrapped if i < len(w)) * text.line_height(itf) for i in range(n)]
        gap = round(text.line_height(itf) * 0.5)
        rows_h = sum(heights) + gap * max(0, n - 1)
        tall = max((len(b) for w in wrapped for b in w), default=0)
        if (tall <= LIST_MAX_LINES and fits(rows_h, gap, itf)) or itf.size < 26:
            break
        itf = font(itf.size * 0.97, family=PRINT)
    widest = max((text.measure(ln, itf) for w in wrapped for b in w for ln in b), default=0)
    return dict(font=itf, heights=heights, gap=gap, rows_h=rows_h, wrapped=wrapped,
                check=check, cx=0, tx=check + 30 * u, widest=widest)


def list_rows_items(items_text, rows, lines, L, x, y, f0, f1):
    """A checklist's rows drawn at (x, y) in the shape `rows` (list_rows):
    each a hand-drawn check mark then its text, revealed one per line like
    a `timeline` but with no dates (docs/SCRIPT-FORMAT.md). Returns (items,
    Box of the rows, the same size for every list laid out by `rows`)."""
    u = L['u']
    itf, check = rows['font'], rows['check']
    n = len(items_text)
    starts = timeline_reveals(n, lines, f0)
    cx0, tx = x + rows['cx'], x + rows['tx']
    items = []
    top = y
    for i, (it, h, s0) in enumerate(zip(items_text, rows['heights'], starts)):
        block = list_wrap(it, itf, rows['width'])
        cy = y + text.line_height(itf) * 0.5
        mark = Stroke(check_mark_pts(cx0 + check / 2, cy, check), seed_of('check', i), passes=2,
                     width=4.6 * u, overshoot=0)
        entry = [stroke_item(s0, s0 + 9, mark, ink=LIST_COLOUR)]
        ti, _, _ = write_lines(s0 + 9, block, itf, tx, y)
        entry += ti
        nxt = starts[i + 1] if i + 1 < n else f1
        items += scaled(entry, s0, draw_budget(s0, nxt))
        y += h + rows['gap']
    return items, Box(cx0, top, tx + rows['widest'] - cx0, rows['rows_h'])


def source_lines(chart, L, width):
    """'Source: ...' wrapped to `width`: (lines, height)."""
    nf = L['note_font']
    slines = text.wrap(f'Source: {chart.source.short_credit}', nf, width, balance=True)
    return slines, text.line_height(nf) * len(slines)


def source_at(chart, L, f0, box):
    """'Source: ...' centred in `box` from its top, on the page from f0 for
    as long as its visual is (rule 7.1): (item, box)."""
    nf = L['note_font']
    slines, sh = source_lines(chart, L, box.w)

    def draw_source(cv, p):
        sp.pencil_text(cv, slines, nf, box.x, box.y, GRAPHITE, 0.85, align='center', width=box.w)
    return Item(f0 - 1, f0, draw_source, None, ease=vb.linear), Box(box.x, box.y, box.w, sh)


def list_visual(chart, lines, L, f0, f1, stage=None, peers=()):
    """A checklist in a column, top to bottom: a side's own points, in short
    form (the second exception to pictures-only on the stage, besides the
    page card). Each entry is a hand-drawn check mark then its text,
    revealed one per line like a `timeline` but with no dates
    (docs/SCRIPT-FORMAT.md), and the source along the bottom. `stage`
    overrides L['stage'], for a list confined to less than the whole
    stage (the sides slide's two blocks, sides_group). `peers` are other
    lists' items to lay out alike: the font, each row's height, the gaps
    and the column's offsets are fitted to all of them together, so two
    side blocks line up row for row whatever their words (rule 7.4)."""
    v = chart.visual
    stage = stage if stage is not None else L['stage']
    u = L['u']
    src, sbox = source_note(chart, L, f0, stage)
    itf = L['timeline_font']
    n = len(v.items)
    check = 40 * u
    tx0 = stage.x + check + 30 * u
    tw = stage.right - tx0
    every = [v.items, *peers]
    while True:
        blocks = [text.wrap(it, itf, tw, balance=True) for it in v.items]
        heights = [max(len(text.wrap(its[i], itf, tw, balance=True)) for its in every if i < len(its))
                   * text.line_height(itf) for i in range(n)]
        room = sbox.y - 40 * u - stage.y
        if sum(heights) + 36 * u * (n - 1) <= room or itf.size < 26:
            break
        itf = font(itf.size * 0.92, family=PRINT)
    gap = max(36 * u, min(100 * u, (room - sum(heights)) / max(1, n - 1)))
    # centre the column on the stage, as timeline_visual does
    widest = max(text.measure(ln, itf) for its in every for it in its
                 for ln in text.wrap(it, itf, tw, balance=True))
    shift = max(0, (stage.w - (tx0 - stage.x) - widest) / 2 - 20 * u)
    cx0, tx = stage.x + shift, tx0 + shift
    y = stage.y + max(0, (room - sum(heights) - gap * (n - 1)) / 2)
    starts = timeline_reveals(n, lines, f0)
    items = [src]
    top = y
    for i, (block, h, s0) in enumerate(zip(blocks, heights, starts)):
        cy = y + text.line_height(itf) * 0.5
        entry = []
        f = s0
        mark = Stroke(check_mark_pts(cx0 + check / 2, cy, check), seed_of('check', i), passes=2,
                     width=4.6 * u, overshoot=0)
        entry.append(stroke_item(f, f + 9, mark, ink=LIST_COLOUR))
        f += 9
        ti, f, _ = write_lines(f, block, itf, tx, y)
        entry += ti
        nxt = starts[i + 1] if i + 1 < n else f1
        items += scaled(entry, s0, draw_budget(s0, nxt))
        y += h + gap
    box = Box(cx0, top, stage.right - cx0, y - gap - top)
    return items, [Mark('chart', box), Mark('chart source', sbox)]


# ---- the stage: both sides on one slide (STANDARD.md rule 2.2) ----
# A fixed heading (not the sections' own: this slide covers both of them)
# over two congruent blocks, one per side, in play order: top/bottom in
# 9:16, left/right in 16:9. Each block is labelled with its own section's
# heading and, if it has one, draws its own 'list' on its own narration's
# clock; a side with none shows just its label. The two blocks are laid
# out together (sides_plan), so nothing about them differs but their
# words and order: the same label and item font, row heights, gaps and
# offsets (rule 7.4). When both lists cite the same source, the slide
# prints it once, under both blocks; otherwise each block prints its own,
# in the same place in each. Each block sits in its own pencilled card,
# both the same size.
SIDES_HEADING = 'What each side says'
EDGE_GAP = 32   # px from the heading's underline to the first card, and from the source line to the caption
CARD_GAP = 40   # px between the two cards
LABEL_GAP = 22  # px between a block's label and its rows
SOURCE_GAP = 30  # px above a source line
CARD_PAD = 24   # px inside a card, at least, above and below its block, and exactly this at its sides
ITEM_MAX = 0.7    # the items' font grows to at most this much of the page heading's...
LABEL_SCALE = 1.25  # ...and the labels' to this much of the items', room allowing
LABEL_MAX = 0.8   # but never past this much of the page heading's


def sides_room(L):
    """The top and bottom of the room the sides slide fills: from just
    under the fixed heading's underline to just above the caption."""
    _, _, h_box = heading_text_items(SIDES_HEADING, L, 0)
    gap = EDGE_GAP * L['u']
    return h_box.bottom + gap, L['scrap'].y - gap


def block_label_font(secs, L, width, size):
    """The block labels' font, one for both: the largest, from `size`
    down, at which neither takes more than two lines across `width`."""
    fnt = font(size, 700)
    while True:
        n = max(len(text.wrap(s.section.heading, fnt, width, balance=True)) for s in secs)
        if n <= 2 or fnt.size < 24:
            return fnt, n * text.line_height(fnt)
        fnt = font(fnt.size * 0.92, 700)


def block_heading_items(sec, L, box, f0, fnt):
    """A block's own label, centred along the top of `box` and underlined
    in orange, as heading_text_items does for the page heading."""
    lines = text.wrap(sec.section.heading, fnt, box.w, balance=True)
    items, f, drawn = write_lines(f0, lines, fnt, box.x, box.y, align='center', width=box.w, speed=1.4)
    w = max(text.measure(ln, fnt) for ln in lines)
    uy = drawn.bottom + 2
    under = Stroke(sp.catmull([(box.cx - w / 2 - 5, uy + 1), (box.cx, uy - 1), (box.cx + w / 2 + 8, uy + 2)],
                              per=10), seed_of('block-underline'), passes=2, width=4 * L['u'])
    items.append(stroke_item(f + 1, f + 7, under, ORANGE))
    return items, f + 7, Box(box.cx - w / 2 - 5, box.y, w + 13, uy + 8 - box.y)


def side_list(sec):
    """A side's 'list' run (kind, chart, lines), or None."""
    return next((r for r in runs_of(sec) if r[0] == 'chart' and r[1].visual.kind == 'list'), None)


def sides_plan(side_a, side_b, L, fmt):
    """Where everything on the sides slide goes, both blocks fitted
    together: a dict of the label font and height, the rows (list_rows),
    each card's box, each block's box inside its card (the label at its
    top, the rows under it), and the shared source's box, if any.

    The two cards fill the room between the heading and the caption
    (sides_room), the same size, CARD_GAP apart; the shared source line,
    if any, ends at the room's bottom. Their height goes to the text
    first: the largest item font (the labels' growing with it) at which
    everything fits with the rows at their least gap and the cards at
    their least padding; what height is left is shared out evenly
    between the gaps between rows and the cards' padding above and below,
    so none of it collects in one place."""
    u = L['u']
    st = L['stage']
    top, bottom = sides_room(L)
    secs = (side_a, side_b)
    runs = [side_list(s) for s in secs]
    charts = [r[1] for r in runs if r]
    shared = len(charts) == 2 and charts[0].source.id == charts[1].source.id
    stacked = fmt == '9x16'
    pad = CARD_PAD * u
    gap = CARD_GAP * u
    outer_w = st.w if stacked else (st.w - gap) / 2
    bw = outer_w - 2 * pad
    label_gap = LABEL_GAP * u
    src_gap = SOURCE_GAP * u
    src_h = max((source_lines(c, L, st.w if shared else bw)[1] for c in charts), default=0)
    # what goes under the rows in each block, and under both blocks
    own_src = src_gap + src_h if charts and not shared else 0
    foot = src_gap + src_h if shared else 0
    room = bottom - top - foot
    card_h = (room - gap) / 2 if stacked else room
    heading = L['heading_font'].size

    def label_for(itf):
        return block_label_font(secs, L, bw, min(itf.size * LABEL_SCALE, heading * LABEL_MAX))

    def block_h(rows_h, itf):
        return label_for(itf)[1] + (label_gap + rows_h + own_src if charts else 0)

    def fits(rows_h, row_gap, itf):
        return block_h(rows_h, itf) + 2 * pad <= card_h

    rows = list_rows([c.visual.items for c in charts], L, bw, fits, heading * ITEM_MAX)
    rows['width'] = bw - rows['tx']
    label_f, label_h = label_for(rows['font'])
    # the height left over, shared out between the padding above and
    # below each block and the gaps between its rows
    n = len(rows['heights'])
    spare = max(0, card_h - 2 * pad - block_h(rows['rows_h'], rows['font']))
    share = spare / (n + 1) if charts else spare / 2
    if charts and n > 1:
        rows['gap'] += share
        rows['rows_h'] += share * (n - 1)
    pad_y = pad + share
    if stacked:
        cards = [Box(st.x, top, st.w, card_h), Box(st.x, top + card_h + gap, st.w, card_h)]
    else:
        cards = [Box(st.x, top, outer_w, card_h), Box(st.x + outer_w + gap, top, outer_w, card_h)]
    blocks = [Box(c.x + pad, c.y + pad_y, c.w - 2 * pad, c.h - 2 * pad_y) for c in cards]
    return dict(label_font=label_f, label_h=label_h, rows=rows, blocks=blocks, cards=cards,
                source=Box(st.x, bottom - src_h, st.w, src_h) if shared else None)


def side_block(sec, L, box, label_f0, plan):
    """One side's whole block in `box` (sides_plan): its label, drawn at
    `label_f0` (the same frame for both sides, when the slide appears),
    and, if it has a 'list' visual, that list ticking in on the side's own
    lines under it, exactly as runs_of/chart_run schedule it for a single
    side, and its own source under the rows unless the slide prints one
    for both. Returns (items, marks, the list's first frame or None)."""
    u = L['u']
    items, label_end, label_box = block_heading_items(sec, L, box, label_f0, plan['label_font'])
    marks = [Mark('heading', label_box, label_f0)]
    run = side_list(sec)
    if run is None:
        return items, marks, None
    _, chart, lines = run
    start = lines[0].start
    first_f = max(label_end + 2, start + (FADE if start > sec.start else 0))
    rows = plan['rows']
    y = box.y + plan['label_h'] + LABEL_GAP * u
    list_items, rbox = list_rows_items(chart.visual.items, rows, lines, L, box.x, y, first_f, chart.end)
    items += list_items
    marks.append(Mark('chart', rbox, first_f))
    if plan['source'] is None:
        src, sbox = source_at(chart, L, first_f, Box(box.x, y + rows['rows_h'] + SOURCE_GAP * u, box.w, 0))
        items.append(src)
        marks.append(Mark('chart source', sbox, first_f))
    return items, marks, first_f


def card_items(box, L, f0):
    """A light pencilled box around a block, seeded alike for
    both so the two come out the same shape."""
    outline = Stroke(box_pts(box.x, box.y, box.w, box.h), seed_of('side card'), passes=2,
                     width=3 * L['u'], closed=True, overshoot=0, alpha=0.5)
    return [stroke_item(f0, f0 + 14, outline)]


def sides_group(side_a, side_b, L, fmt, h_f0):
    """Both side sections as one slide: the fixed heading, then the two
    blocks (side_block) in play order where sides_plan puts them, side_a
    first, and the shared source line under both if they share one."""
    h_items, h_end, h_box = heading_text_items(SIDES_HEADING, L, h_f0)
    plan = sides_plan(side_a, side_b, L, fmt)
    items = list(h_items)
    marks = [Mark('heading', h_box, side_a.start)]
    label_f0 = h_end + 2
    for card in plan['cards']:
        items += card_items(card, L, label_f0)
    label_f0 += 14
    firsts = []
    for sec, box in zip((side_a, side_b), plan['blocks']):
        si, sm, first = side_block(sec, L, box, label_f0, plan)
        items += si
        marks += sm
        if first is not None:
            firsts.append(first)
    if plan['source'] is not None:
        f0 = min(firsts)
        src, sbox = source_at(side_list(side_a)[1], L, f0, plan['source'])
        items.append(src)
        marks.append(Mark('chart source', sbox, f0))
    return items, marks


SHARE_HATCH = [dict(angle=45, spacing=11, cross=False, alpha=0.5),
               dict(angle=-35, spacing=8, cross=True, alpha=0.36),
               dict(angle=0, spacing=13, cross=False, alpha=0.5),
               dict(angle=80, spacing=9, cross=False, alpha=0.45),
               dict(angle=20, spacing=15, cross=True, alpha=0.3)]


def share_chart(chart, L, f0, f1):
    """One column divided into parts, top to bottom in the labels' order,
    each labelled to its right with its value; it is the whole (100), so it
    starts at zero (rule 7.2). A single part fills it from the bottom."""
    v = chart.visual
    u = L['u']
    items, f, plot, tbox, sbox = chart_frame(chart, L, f0)
    lf, vf = L['chart_label_font'], L['value_font']
    n = len(v.values)
    col_w = 210 * u
    gap = 70 * u
    label_w = min(plot.w - col_w - gap, 640 * u)
    gx = plot.cx - (col_w + gap + label_w) / 2
    ch = plot.h
    cy0 = plot.y
    outline = Stroke(box_pts(gx, cy0, col_w, ch), seed_of('share col'), passes=3, width=4 * u, closed=True,
                     overshoot=2)
    items.append(stroke_item(f, f + 16, outline))
    f += 16
    # where each label goes: beside its part, pushed apart if parts are thin,
    # in type small enough that all of them fit beside the column
    gap = 12 * u
    while True:
        blocks = []
        # one part alone sits at the bottom, a level: this much of the whole
        y = cy0 + ch * (1 - v.values[0] / 100) if n == 1 else cy0
        for i, (lb, val) in enumerate(zip(v.labels, v.values)):
            h = ch * val / 100
            ls = text.wrap(str(lb), lf, label_w, balance=True)
            bh = text.line_height(lf) * len(ls) + text.line_height(vf)
            blocks.append(dict(y=y, h=h, lines=ls, bh=bh, val=val, i=i))
            y += h
        if sum(b['bh'] for b in blocks) + gap * (len(blocks) - 1) <= ch or lf.size < 22:
            break
        lf, vf = font(lf.size * 0.92, 600), font(vf.size * 0.92, 700)
    floor = cy0
    for b in blocks:
        b['ly'] = max(floor, b['y'] + b['h'] / 2 - b['bh'] / 2)
        floor = b['ly'] + b['bh'] + gap
    ceiling = cy0 + ch
    for b in reversed(blocks):
        b['ly'] = min(b['ly'], ceiling - b['bh'])
        ceiling = b['ly'] - gap
    for b in blocks:
        y, h = b['y'], b['h']
        if b['i'] > 0:
            div = Stroke([(gx, y), (gx + col_w, y)], seed_of('div', b['i']), passes=2, width=3.4 * u)
            items.append(stroke_item(f, f + 6, div))
            f += 6
        hs = SHARE_HATCH[b['i'] % len(SHARE_HATCH)]
        if h > 4:
            hatch = Hatch(box_pts(gx, y, col_w, h), seed_of('share', b['i']), angle=hs['angle'],
                          spacing=hs['spacing'] * u, cross=hs['cross'], alpha=hs['alpha'], width=2.2 * u)
            items.append(hatch_item(f, f + 16, hatch, ink=SHARE_COLOUR))
            f += 16
        lx = gx + col_w + gap
        mid = y + h / 2
        lead_y = b['ly'] + text.line_height(lf) * 0.6
        leader = Stroke([(gx + col_w + 8 * u, mid), (lx - 14 * u, lead_y)], seed_of('lead', b['i']), passes=1,
                        width=2.4 * u, overshoot=0, alpha=0.7)
        items.append(stroke_item(f, f + 4, leader, pencil=False))
        li, f, _ = write_lines(f + 2, b['lines'], lf, lx, b['ly'])
        items += li
        vi, f, _ = write_lines(f, [with_unit(b['val'], v.unit)], vf, lx,
                               b['ly'] + text.line_height(lf) * len(b['lines']))
        items += vi
        f += 6
    items = scaled(items, f0, draw_budget(f0, f1))
    return items, [Mark('chart', Box(plot.x, tbox.y, plot.w, plot.bottom - tbox.y)), Mark('chart source', sbox)]


def axis_ticks(lo, hi, most=5):
    """Round values for a y axis over lo..hi: zero, and steps of 1, 2, 2.5 or
    5 times a power of ten, at most `most` of them in all."""
    span = hi - lo
    mag = 10 ** math.floor(math.log10(span)) if span > 0 else 1
    for m in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10):
        step = m * mag
        k0, k1 = math.ceil(lo / step - 1e-9), math.floor(hi / step + 1e-9)
        if k1 - k0 + 1 <= most:
            return [round(k * step, 10) for k in range(k0, k1 + 1)]
    return [0.0]


def series_chart(chart, L, f0, f1):
    """A line over time: x positions evenly spaced (rule 7.2), the y axis
    running from zero (or the lowest value, if below zero) to the highest,
    with its values at round steps, and the last point's value beside it."""
    v = chart.visual
    u = L['u']
    items, f, plot, tbox, sbox = chart_frame(chart, L, f0)
    nf, vf = L['axis_font'], L['chart_label_font']
    vals = [float(x) for x in v.values]
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    if hi == lo:
        hi = lo + 1
    n = len(vals)
    ticks = axis_ticks(lo, hi)
    tick_w = max(text.measure(with_unit(tv, v.unit), nf) for tv in ticks)
    end_label = with_unit(vals[-1], v.unit)
    x0, x1 = plot.x + 56 * u + tick_w, plot.right - 30 * u - text.measure(end_label, vf)
    base_lab = text.line_height(nf) + 10 * u
    yt, yb = plot.y + text.line_height(vf) + 10 * u, plot.bottom - base_lab - text.line_height(vf) * 0.6
    ys = lambda val: yb - (val - lo) / (hi - lo) * (yb - yt)  # noqa: E731
    xs = lambda i: x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5)  # noqa: E731
    zero = ys(0)
    items.append(stroke_item(f, f + 12, Stroke([(x0 - 30 * u, zero), (x1 + 30 * u, zero)], seed_of('s axis'),
                                               passes=3, width=4 * u)))
    items.append(stroke_item(f, f + 12, Stroke([(x0 - 30 * u, yb + 10), (x0 - 30 * u, yt - 10)],
                                               seed_of('s yaxis'), passes=2, width=3 * u), pencil=False))
    # value labels up the y axis: zero and round steps (rule 7.2)
    for tv in ticks:
        ty = ys(tv)
        if tv:
            tick = Stroke([(x0 - 40 * u, ty), (x0 - 20 * u, ty)], seed_of('tick', tv), passes=1, width=3 * u,
                          overshoot=0)
            items.append(stroke_item(f + 8, f + 10, tick, pencil=False))
        items.append(text_item(f + 8, f + 12, with_unit(tv, v.unit), nf, x0 - 46 * u, ty - text.line_height(nf) / 2,
                               alpha=0.8, align='right', pencil=False))
    f += 14
    lab_w = max(text.measure(str(lb), nf) for lb in v.labels) + 30 * u
    step = max(1, math.ceil(n * max(120 * u, lab_w) / (x1 - x0)))
    for i, lb in enumerate(v.labels):
        # every step-th label, and the last one, unless too close to it
        if i != n - 1 and (i % step or xs(n - 1) - xs(i) < lab_w):
            continue
        items.append(text_item(f, f + 3, str(lb), nf, xs(i), yb + 14 * u, alpha=0.85, align='center',
                               pencil=False))
        f += 1.5
    pts = [(xs(i), ys(val)) for i, val in enumerate(vals)]
    line = Stroke(pts, seed_of('series'), passes=3, width=4.4 * u, wobble=1.2, overshoot=0)
    d = max(30, 6 * n)
    items.append(stroke_item(f, f + d, line, ink=SERIES_COLOUR))
    f += d
    # the last point's value, beside it, so the line's end can be read
    x, y = pts[-1]
    dot = Stroke(sp.ellipse(x, y, 7 * u, 7 * u, n=16), seed_of('dot', n - 1), passes=2, width=3.6 * u,
                 closed=True, overshoot=0)
    items.append(stroke_item(f, f + 3, dot, ink=SERIES_COLOUR, pencil=False))
    li, f, _ = write_lines(f, [end_label], vf, x + 16 * u, y - text.line_height(vf) * 0.55)
    items += li
    items = scaled(items, f0, draw_budget(f0, f1))
    return items, [Mark('chart', Box(plot.x, tbox.y, plot.w, plot.bottom - tbox.y)), Mark('chart source', sbox)]


def figure_steady_spending_volatile_revenue(chart, L, f0, f1):
    """The LAO's schematic: a smooth, gently rising spending line, and a
    revenue line swinging above it (surplus years) and below it (deficit
    years). No numbers and no axis values, as in the LAO's own figure."""
    u = L['u']
    items, f, plot, tbox, sbox = chart_frame(chart, L, f0)
    lf = L['chart_label_font']
    lab_w = text.measure('Spending', lf) + 20 * u
    x0, x1 = plot.x + 40 * u, plot.right - lab_w - 10 * u
    yb, yt = plot.bottom - 10 * u, plot.y + 30 * u
    N = 120

    def at(t, v):
        return (x0 + (x1 - x0) * t, yb - (yb - yt) * v)

    spend = [at(i / N, 0.34 + 0.26 * (i / N) + 0.03 * (i / N) ** 2) for i in range(N + 1)]

    def rev_v(t):
        trend = 0.34 + 0.26 * t + 0.03 * t * t
        amp = 0.11 + 0.08 * math.sin(math.pi * t * 1.3 + 0.4) ** 2
        return trend + amp * math.sin(2 * math.pi * (2.25 * t + 0.08))
    rev = [at(i / N, rev_v(i / N)) for i in range(N + 1)]
    ax = Stroke([(x0 - 10 * u, yt - 20 * u), (x0 - 10 * u, yb), (x1 + 20 * u, yb)], seed_of('fig axes'),
                passes=2, width=3.6 * u, overshoot=3)
    items.append(stroke_item(f, f + 14, ax))
    f += 16
    sl = Stroke(spend, seed_of('spend'), passes=3, width=5 * u, wobble=0.8, overshoot=0)
    items.append(stroke_item(f, f + 26, sl, ink=SPENDING_COLOUR))
    f += 26
    ex, ey = spend[-1]
    si, f, sbx = write_lines(f + 2, ['Spending'], lf, ex + 14 * u, ey - text.line_height(lf) * 0.55)
    items += si
    rl = Stroke(rev, seed_of('rev'), passes=3, width=4.4 * u, wobble=1.2, overshoot=0)
    items.append(stroke_item(f + 4, f + 44, rl, ink=REVENUE_COLOUR))
    f += 46
    # the revenue label beside the line's highest swing, above it
    k = max(range(N + 1), key=lambda i: rev_v(i / N) - (0.34 + 0.26 * i / N + 0.03 * (i / N) ** 2)
            if 0.15 < i / N < 0.8 else -9)
    rx, ry = rev[k]
    ri, f, _ = write_lines(f + 2, ['Revenue'], lf, rx - text.measure('Revenue', lf) / 2,
                           ry - text.line_height(lf) - 12 * u)
    items += ri
    items = scaled(items, f0, draw_budget(f0, f1))
    return items, [Mark('chart', Box(plot.x, tbox.y, plot.w, plot.bottom - tbox.y)), Mark('chart source', sbox)]


# The Rainy Day Fund, as drawn in the style mock (film/mocks/sketchbook.py,
# scene 2): an umbrella sheltering a jar of coins from the rain. The
# geometry is the mock's, in its 1080x1920 page space; figure_rainy_day_fund
# fits it to the plot box.
FUND_C = (560, 540)    # canopy centre
FUND_ROT = -0.24       # canopy tilted to shelter the jar
FUND_RX, FUND_RY = 370, 290
FUND_RIBS = 6
FUND_COINS = [(1104, [318, 388, 456, 523]), (1060, [352, 422, 490]), (1018, [386, 456])]


def _fund_geometry():
    cr, sr = math.cos(FUND_ROT), math.sin(FUND_ROT)
    cx, cy = FUND_C

    def tilt(pts):
        return [(cx + x * cr - y * sr, cy + x * sr + y * cr) for x, y in pts]

    def rib(xk):
        return [(xk * math.sin(t * math.pi / 2 / 20), -FUND_RY * math.cos(t * math.pi / 2 / 20)) for t in range(21)]

    def scallop(xa, xb):
        return [(xa + (xb - xa) * t / 12, -30 * math.sin(math.pi * t / 12)) for t in range(13)]

    edges = [-FUND_RX + k * 2 * FUND_RX / FUND_RIBS for k in range(FUND_RIBS + 1)]
    scallops = [tilt(scallop(a, b)) for a, b in zip(edges, edges[1:])]
    hook = tilt([(0, 560)] + [(38 - 38 * math.cos(t * math.pi / 14), 560 + 38 * math.sin(t * math.pi / 14))
                              for t in range(1, 15)] + [(76, 548)])
    return dict(
        top=tilt(sp.ellipse(0, 0, FUND_RX, FUND_RY, math.pi, 2 * math.pi, n=60)),
        hem=[p for sc in scallops for p in sc[:-1]] + [scallops[-1][-1]],
        ribs=[tilt(rib(x)) for x in edges[1:-1]],
        panels=[tilt(rib(a) + scallop(a, b)[1:] + rib(b)[::-1][1:]) for a, b in zip(edges, edges[1:])],
        shaft=(tilt([(0, -FUND_RY - 42), (0, -FUND_RY)]), tilt([(0, -8), (0, 560)]) + hook[1:]),
        jar=sp.catmull([(300, 790), (300, 818), (276, 852), (274, 960), (274, 1108), (300, 1146), (420, 1150),
                        (540, 1146), (566, 1108), (566, 960), (564, 852), (540, 818), (540, 790)], per=8),
        rim=sp.ellipse(420, 790, 122, 17),
        ground=[(190, 1160), (470, 1156), (840, 1161)],
    )


def figure_rainy_day_fund(chart, L, f0, f1):
    """The Rainy Day Fund: rain falling, an umbrella over a jar, and coins
    that drop into the jar as it is drawn. No numbers. Once drawn it holds
    still: the rain is a few still pencil streaks, not a loop."""
    u = L['u']
    items, f, plot, tbox, sbox = chart_frame(chart, L, f0)
    g = _fund_geometry()
    # the mock's drawing spans x 150..950, y 200..1185; fit that to the plot
    mx0, my0, mw, mh = 150, 200, 800, 985
    k = min(plot.w / mw, plot.h / mh)
    ox, oy = plot.cx - mw * k / 2, plot.y + (plot.h - mh * k) / 2
    kw = max(k, 0.6) * u  # lines no thinner than a readable pencil

    def P(pts):
        return [(ox + (x - mx0) * k, oy + (y - my0) * k) for x, y in pts]

    def S(pts, seed, passes=2, width=3.4, **kw_):
        return Stroke(P(pts), seed_of('fund', seed), passes=passes, width=width * kw, **kw_)

    t0 = f  # the mock's frame 258
    def at(mock_frame):  # noqa: E306
        return t0 + (mock_frame - 258)

    # rain: still streaks, stopped by the canopy, faded in under the drawing
    canopy = P(g['top'])

    def canopy_y(x):
        for (x0, y0), (x1, y1) in zip(canopy, canopy[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return None
    drops = []
    ground = oy + (1150 - my0) * k
    for i in range(40):
        x = ox + random.Random(70 + i).uniform(0.02, 0.98) * mw * k
        y = oy + random.Random(170 + i).uniform(0, 0.9) * (ground - oy)
        stop = canopy_y(x)
        if y + 26 * k > (stop if stop is not None else ground):
            continue
        drops.append((x, y))

    def rain(cv, p):
        ctx = cv.ctx
        ctx.save()
        ctx.new_path()
        for x, y in drops:
            ctx.move_to(x, y)
            ctx.line_to(x - 5 * k, y + 26 * k)
        ctx.set_line_width(2.6 * kw)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source(sp.ink(GRAPHITE, 0.45 * p))
        ctx.stroke()
        ctx.restore()
    items.append(Item(at(280), at(300), rain, None, ease=vb.linear))
    # canopy: the top in one sweep, then the scalloped hem, ribs, shaft and hook
    items.append(stroke_item(at(258), at(272), S(g['top'], 'top', passes=3, width=4.4)))
    items.append(stroke_item(at(272), at(280), S(g['hem'], 'hem', width=3.8), pencil=False))
    for i, r in enumerate(g['ribs']):
        items.append(stroke_item(at(276 + 1.6 * i), at(279 + 1.6 * i), S(r, ('rib', i), width=3), pencil=False))
    items.append(stroke_item(at(278), at(281), S(g['shaft'][0], 'tip', width=5), pencil=False))
    items.append(stroke_item(at(280), at(288), S(g['shaft'][1], 'shaft', passes=3, width=5.4), pencil=False))
    for i in (4, 5):
        h = Hatch(P(g['panels'][i]), seed_of('fund panel', i), angle=-58, spacing=13 * kw, cross=i == 5,
                  alpha=0.38, width=2.2 * kw)
        items.append(hatch_item(at(282 + 4 * (i - 4)), at(296), h, ink=FUND_CANOPY_COLOUR, pencil=False))
    # the jar, its rim, a glint on the glass, its shadow on the ground
    items.append(stroke_item(at(298), at(312), S(g['jar'], 'jar', passes=3, width=4)))
    items.append(stroke_item(at(312), at(318), S(g['rim'], 'rim', width=3.4, closed=True)))
    for i, (x0, y0, y1) in enumerate(((296, 880, 990), (304, 1010, 1040))):
        items.append(stroke_item(at(318), at(320), S([(x0, y0), (x0 - 2, y1)], ('glint', i), passes=1, width=3,
                                                      alpha=0.5), pencil=False))
    items.append(hatch_item(at(318), at(330), Hatch(P([(530, 860), (556, 880), (556, 1100), (530, 1130)]),
                                                     seed_of('fund glass'), angle=80, spacing=10 * kw, alpha=0.32,
                                                     width=2.2 * kw), pencil=False))
    items.append(stroke_item(at(316), at(324), S(g['ground'], 'ground', width=3), pencil=False))
    items.append(hatch_item(at(320), at(332), Hatch(P(sp.ellipse(450, 1160, 200, 14)), seed_of('fund shadow'),
                                                     angle=20, spacing=8 * kw, alpha=0.4, width=2.2 * kw),
                            pencil=False))
    # coins dropping into the jar, one after another, as it is drawn
    rnd = random.Random(50)
    j = 0
    for y, xs in FUND_COINS:
        for x in xs:
            ry, rot = rnd.uniform(0.4, 0.95), rnd.uniform(-0.5, 0.5)
            cx, cy = P([(x + rnd.uniform(-4, 4), y + rnd.uniform(-3, 3))])[0]
            outer = Stroke(sp.ellipse(0, 0, 33 * k, 33 * k * ry, rot=rot, n=36), seed_of('coin', j), passes=2,
                           width=3 * kw, closed=True)
            inner = Stroke(sp.ellipse(0, 0, 22 * k, 22 * k * ry, rot=rot, n=30), seed_of('coin in', j), passes=1,
                           width=2 * kw, alpha=0.5, closed=True)
            fill = Hatch(sp.ellipse(0, 0, 30 * k, 30 * k * ry, rot=rot, n=24), seed_of('coin fill', j), angle=40,
                         spacing=7 * kw, alpha=0.5, width=2 * kw)
            drop = (y - 660) * k
            spin = rnd.uniform(-3, 3)

            def coin(cv, p, cx=cx, cy=cy, outer=outer, inner=inner, fill=fill, drop=drop, spin=spin):
                ctx = cv.ctx
                ctx.save()
                ctx.translate(cx, cy - drop * (1 - p * p))  # falls with gravity
                ctx.rotate((1 - p) * spin)
                fill.draw(cv, 1.0, FUND_COIN_COLOUR, 0.9)
                outer.draw(cv, 1.0)
                inner.draw(cv, 1.0)
                ctx.restore()
            items.append(Item(at(306 + 2.6 * j), at(317 + 2.6 * j), coin, None, ease=vb.linear))
            j += 1
    items = scaled(items, f0, draw_budget(f0, f1))
    return items, [Mark('chart', Box(plot.x, tbox.y, plot.w, plot.bottom - tbox.y)), Mark('chart source', sbox)]


FIGURES = {
    'rainy-day-fund': figure_rainy_day_fund,
    'steady-spending-volatile-revenue': figure_steady_spending_volatile_revenue,
}
CHARTS = {'bars': bars_chart, 'share': share_chart, 'series': series_chart}
SHOWN = {'illustration': illustration_visual, 'timeline': timeline_visual, 'list': list_visual}


def chart_run(chart, lines, L, first_f):
    """The visual `chart` on the stage, for `lines` (its own and the ones
    it stays up for): (items, marks)."""
    v = chart.visual
    if v.kind == 'figure':
        if v.figure not in FIGURES:
            raise ValueError(f'{chart.section}.line[{chart.index}]: unknown figure {v.figure!r}; '
                             f'this template draws {sorted(FIGURES)}')
        return FIGURES[v.figure](chart, L, first_f, chart.end)
    if v.kind in SHOWN:
        return SHOWN[v.kind](chart, lines, L, first_f, chart.end)
    if v.kind not in CHARTS:
        raise ValueError(f'{chart.section}.line[{chart.index}]: unknown chart kind {v.kind!r}')
    return CHARTS[v.kind](chart, L, first_f, chart.end)


# ---- a section's page ----
class Group:
    """Items drawn on together and faded out together: on the page from
    frame `f0`, fading out over FADE frames from `out` (None: never), with
    the marks they show while fully up."""

    def __init__(self, items, marks, f0, out=None, hidden=None):
        self.items, self.marks, self.f0, self.out = items, marks, f0, out
        self.hidden = hidden  # a heading: how far the full-page view hides it at frame n, 0..1

    def draw(self, cv, n):
        if n < self.f0 - 1 or (self.out is not None and n >= self.out + FADE):
            return
        h = self.hidden(n) if self.hidden else 0
        if h >= 1:
            return
        if h > 0:
            out = 1 if self.out is None or n < self.out else 1 - (n - self.out) / FADE
            with cv.layer(opacity=(1 - h) * out):
                for it in self.items:
                    it.draw(cv, n)
            return
        if self.out is None or n < self.out:
            for it in self.items:
                it.draw(cv, n)
            for m in self.marks:
                if n >= m.f0:
                    cv.mark(m.name, *m.box)
            return
        with cv.layer(opacity=1 - (n - self.out) / FADE):
            for it in self.items:
                it.draw(cv, n)


def runs_of(sec):
    """The section's stage, run by run: ('chart', ChartBeat, lines) for each
    visual and the lines it is up for (its own, and the ones after it until
    the next visual or the section's end), and ('ballot', None, lines) for
    the lines before the first visual in `what` and `vote`. Elsewhere the
    lines before the first visual have nothing on the stage: just the
    heading."""
    lines = sec.lines
    at = [c.index for c in sec.charts]
    out = []
    if not at or at[0] > 0:
        j = at[0] if at else len(lines)
        if sec.section.id in ('what', 'vote'):
            out.append(('ballot', None, lines[:j]))
    for k, c in enumerate(sec.charts):
        j = at[k + 1] if k + 1 < len(at) else len(lines)
        out.append(('chart', c, lines[c.index:j]))
    return out


# ---- the stage: the official page (the `page` visual) ----
# The measure's page in the state's official guide (BALLOT.guide), drawn from the script's
# [card] (docs/SCRIPT-FORMAT.md): the first `page` line draws it on, and
# each one with a `focus` "clicks" a term on it: the highlighter sweeps over
# every occurrence, and the camera holds (PAGE_ZOOM_MAX is 1: the page is
# readable whole). A later `page` line
# brings the page back at full view, every term clicked so far ticked off.
CARD = CONTEST.script.card
PAGE_DRAW = 30     # frames the page takes to draw on, the first time (1 s)
CLICK = 18         # frames the highlighter takes to sweep a term, every occurrence (0.6 s)
ZOOM = 24          # frames the camera takes to ease in on it (0.8 s)
CAMERA = vb.bezier(0.45, 0, 0.55, 1)  # eases in and out
PAGE_ZOOM_MAX = 1.0  # no zoom: the page is readable whole, and any zoom crops its lines
# the badge over the measure's number: its designation, as the guide prints it
BADGE = badge(BALLOT, CONTEST.title, CARD.number) if CARD is not None else None
# the fiscal statement's heading, as the guide prints it: bold where the
# summary quotes it (California's "Fiscal Impact:"), or set over the card's
# own `fiscal` field (Utah's "Fiscal Effects")
FISCAL_LABEL = BALLOT.fiscal_label
# every term the script clicks
PAGE_FOCI = tuple(dict.fromkeys(ln.visual.focus for sec in CONTEST.script.sections for ln in sec.lines
                                if ln.visual is not None and ln.visual.kind == 'page' and ln.visual.focus))


def _space(fnt):
    return text.measure('x x', fnt) - text.measure('xx', fnt)


class Flow:
    """One field of the card set as a paragraph: its words wrapped into
    `width` from (x, y), each word in the plain or bold face. `runs` are
    (text, font, x, y), a line's words of one face, to draw; `boxes(a, b)`
    the boxes on the page of the field's characters a..b, one a line."""

    def __init__(self, field, words, plain, bold=(), bold_font=None, x=0, y=0, width=100, lh=None):
        self.field = field
        self.lh = lh or text.line_height(plain)
        toks = []
        for m in re_words(words):
            a, b = m.span()
            fnt = bold_font if any(s <= a < e for s, e in bold) else plain
            toks.append([a, b, m.group(0), fnt])
        # A term the script clicks is kept on one line where it fits, so the
        # camera can frame it, and its twin in the other box, large.
        kept = []
        for focus in PAGE_FOCI:
            k = words.find(focus)
            while k >= 0:
                kept.append((k, k + len(focus)))
                k = words.find(focus, k + len(focus))
        # (A word belongs to a term when it overlaps it: "2014," still ends
        # "approved by voters in 2014".)
        units = []
        for t in toks:
            if units and any(units[-1][-1][0] < b and units[-1][-1][1] > a and t[0] < b and t[1] > a
                             for a, b in kept):
                units[-1].append(t)
            else:
                units.append([t])

        def unit_width(u):
            return text.measure(' '.join(t[2] for t in u), u[0][3]) if len({id(t[3]) for t in u}) == 1 \
                else sum(text.measure(t[2], t[3]) + _space(t[3]) for t in u)
        # a term too long to keep whole wraps as plain words; the others stay kept
        units = [v for u in units for v in ([[t] for t in u] if len(u) > 1 and unit_width(u) > width else [u])]
        lines = [[]]
        used = 0
        for unit in units:
            w = unit_width(unit)
            gap = _space(unit[0][3]) if lines[-1] else 0
            if lines[-1] and used + gap + w > width:
                lines.append([])
                used, gap = 0, 0
            lines[-1].extend(unit)
            used += gap + w
        self.tokens = []  # (start, end, word, font, x, y)
        self.runs = []
        self.widest = 0
        for i, ln in enumerate(lines):
            ly = y + i * self.lh
            rx = x
            k = 0
            while k < len(ln):
                j = k
                while j < len(ln) and ln[j][3] is ln[k][3]:
                    j += 1
                fnt = ln[k][3]
                run = ' '.join(t[2] for t in ln[k:j])
                for t in ln[k:j]:
                    pre = ' '.join(u[2] for u in ln[k:ln.index(t) + 1])
                    self.tokens.append((t[0], t[1], t[2], fnt, rx + text.measure(pre, fnt) - text.measure(t[2], fnt),
                                        ly))
                self.runs.append((run, fnt, rx, ly))
                rx += text.measure(run, fnt) + (_space(fnt) if j < len(ln) else 0)
                k = j
            self.widest = max(self.widest, rx - x)
        self.x, self.y, self.width = x, y, width
        self.height = self.lh * len(lines)

    def boxes(self, a, b):
        """Boxes covering characters a..b of the field, one per line."""
        by_line = {}
        for s, e, word, fnt, x, y in self.tokens:
            if e <= a or s >= b:
                continue
            la, lb = max(a, s) - s, min(b, e) - s
            x0 = x + (text.measure(word[:la], fnt) if la else 0)
            x1 = x + text.measure(word[:lb], fnt)
            lo, hi = by_line.get(y, (x0, x1))
            by_line[y] = (min(lo, x0), max(hi, x1))
        return [Box(x0, y, x1 - x0, self.lh) for y, (x0, x1) in sorted(by_line.items())]


def re_words(s):
    import re
    return re.finditer(r'\S+', s)


def page_fonts(s):
    return dict(
        body=font(s, family=PRINT), bold=font(s, 700, family=PRINT),
        title=font(s * 1.1, 700, family=PRINT), head=font(s * 0.85, 700, family=PRINT),
        prop=font(s * 0.62, 700, family=PRINT), num=font(s * 1.5, 700, family=PRINT),
        label=font(s * 1.0, 700, family=PRINT))


def page_spreads(card):
    """How many gaps `spread` widens in the stacked arrangement: under the
    title, before the fiscal statement and the vote boxes, between those
    two, and, with the boxes, under their heading and between them."""
    fiscal, votes = card.fiscal is not None, card.yes is not None
    return 1 + (fiscal or votes) + (fiscal and votes) + 2 * votes


def _layout_page(card, box, s, arrangement, spread=0):
    """The card's contents set at body size `s` inside `box`, in one of three
    arrangements: 'stacked' (one column, the YES box over the NO box), 'side'
    (one column, the boxes side by side) or 'columns' (the summary beside
    the fiscal statement and the boxes). `spread` px more go into each of
    the gaps between its blocks (title, summary, fiscal statement, vote
    boxes), so a page with room to spare fills it evenly. The fiscal
    statement and the vote boxes are drawn only when the card has them.
    Returns (height used, parts)."""
    F = page_fonts(s)
    gap = s * 0.55
    pad = s * 0.4           # inside a YES/NO box
    parts = dict(fonts=F, flows=[], shapes=[], labels=[])
    two = arrangement == 'columns'
    colw = (box.w - gap * 1.5) / 2 if two else box.w
    x, y = box.x, box.y
    # the badge: the designation (PROP, AMENDMENT) over the number, in a box, the title beside it
    bw = max(text.measure(BADGE, F['prop']), text.measure(card.number, F['num'])) + s * 0.5
    bh = text.line_height(F['prop']) * 0.85 + text.line_height(F['num']) * 0.8 + s * 0.15
    parts['badge'] = Box(x, y, bw, bh)
    tx = x + bw + gap * 0.8
    title = Flow('title', card.title, F['title'], x=tx, y=y, width=x + colw - tx)
    title.y_shift = max(0, (bh - title.height) / 2)
    title = Flow('title', card.title, F['title'], x=tx, y=y + title.y_shift, width=x + colw - tx)
    parts['flows'].append(title)
    y += max(bh, title.height) + gap * 0.8 + spread
    # SUMMARY, and who put it on the ballot
    sw = text.measure('SUMMARY', F['head'])
    parts['labels'].append(('SUMMARY', F['head'], x, y + (text.line_height(F['body']) - text.line_height(F['head']))))
    origin = Flow('origin', card.origin, F['body'], x=x + sw + gap, y=y, width=colw - sw - gap)
    parts['flows'].append(origin)
    y += max(text.line_height(F['head']), origin.height) + gap * 0.15
    parts['shapes'].append(('rule', (x, y, colw)))
    y += gap * 0.35
    k = card.summary.find(FISCAL_LABEL)
    bold = [(k, k + len(FISCAL_LABEL))] if k >= 0 else []
    summary = Flow('summary', card.summary, F['body'], bold, F['bold'], x=x, y=y, width=colw)
    parts['flows'].append(summary)
    y += summary.height
    left_bottom = y
    votes = card.yes is not None
    if card.fiscal is None and not votes:
        return y - box.y, parts
    if two:
        x, y = box.x + colw + gap * 1.5, box.y
    else:
        y += gap + spread
    if card.fiscal is not None:
        # the fiscal statement, under the guide's own heading for it, in bold
        parts['labels'].append((FISCAL_LABEL, F['bold'], x, y))
        y += text.line_height(F['bold'])
        fiscal = Flow('fiscal', card.fiscal, F['body'], x=x, y=y, width=colw)
        parts['flows'].append(fiscal)
        y += fiscal.height
        if not votes:
            return max(y, left_bottom) - box.y, parts
        y += gap + spread
    # WHAT YOUR VOTE MEANS, then the YES and NO boxes, alike in every way (rule 7.4)
    parts['labels'].append(('WHAT YOUR VOTE MEANS', F['head'], x, y))
    y += text.line_height(F['head']) + gap * 0.05
    parts['shapes'].append(('rule', (x, y, colw)))
    y += gap * 0.5 + spread
    side = arrangement == 'side'
    vw = (colw - gap) / 2 if side else colw
    lab_h = text.line_height(F['label']) * 0.95
    inner = vw - 2 * pad
    flows = [Flow(key, getattr(card, key), F['body'], x=0, y=0, width=inner) for key in ('yes', 'no')]
    vh = pad * 1.6 + lab_h + max(f.height for f in flows)
    step = vh + gap * 0.6 + spread
    for i, (key, word) in enumerate(zip(('yes', 'no'), (w.upper() for w in BALLOT.choices))):
        bx = x + (vw + gap) * i if side else x
        by = y if side else y + step * i
        parts['shapes'].append(('vote', (bx, by, vw, vh)))
        parts['labels'].append((word, F['label'], bx + pad, by + pad * 0.6))
        parts['flows'].append(Flow(key, getattr(card, key), F['body'], x=bx + pad, y=by + pad * 0.6 + lab_h,
                                   width=inner))
    y += vh if side else vh + step
    return max(y, left_bottom) - box.y, parts


@functools.lru_cache(maxsize=4)
def page_plan(fmt):
    """The card laid out for format `fmt` over the full-page view's whole
    stage, at the largest body size that fits, in the arrangement for its
    shape that sets its words largest: (paper box, parts). Room left over
    goes evenly into the gaps between its blocks, and above and below."""
    L = LAYOUTS[fmt]
    paper_box = L['page_stage']
    u = L['u']
    inset = 24 * u
    content = Box(paper_box.x + inset, paper_box.y + inset * 1.3, paper_box.w - 2 * inset, paper_box.h - 2.3 * inset)
    # Stacked boxes in a tall frame, the summary beside them in a wide one:
    # either way a term in both boxes sits close to its twin, so the camera
    # can frame the pair.
    best = None
    # (A card with only a summary has nothing to set beside it.)
    beside = CARD.fiscal is not None or CARD.yes is not None
    for arrangement in (('columns', 'stacked') if L['H'] <= L['W'] and beside else ('stacked',)):
        s = 90 * u
        while s > 12:
            h, parts = _layout_page(CARD, content, s, arrangement)
            if h <= content.h:
                break
            s *= 0.99
        if best is None or s > best[0]:
            best = (s, h, parts, arrangement)
    s, h, parts, arrangement = best
    spread = 0
    if arrangement == 'stacked':
        n = page_spreads(CARD)
        spread = (content.h - h) / (n + 1)
        h += spread * n
    dy = (content.h - h) / 2
    _, parts = _layout_page(CARD, Box(content.x, content.y + dy, content.w, h), s, arrangement, spread)
    parts['arrangement'] = arrangement
    parts['size'] = s
    return paper_box, parts


def focus_boxes(parts, focus):
    """Every occurrence of `focus` on the card, in reading order: a list,
    one entry per occurrence, of its boxes (one per line it spans)."""
    out = []
    for fl in parts['flows']:
        words = getattr(CARD, fl.field)
        k = words.find(focus)
        while k >= 0:
            out.append(fl.boxes(k, k + len(focus)))
            k = words.find(focus, k + len(focus))
    return out


def _tick(b, u, seed):
    """A small tick at the top right of the highlight on box `b`."""
    x, y = b.right + 14 * u, b.y - 4 * u
    s = 15 * u
    return Stroke([(x - s * 0.7, y), (x - s * 0.15, y + s * 0.6), (x + s, y - s * 0.9)], seed, passes=2,
                  width=4 * u, wobble=0.8, overshoot=0)


def page_static(paper_box, parts, L):
    """The page, drawn whole: a draw function for its paper, and the lettering
    and lines on it as (draw(cv, p), head) pairs, in reading order, for
    drawing on."""
    u = L['u']
    F = parts['fonts']
    marks = []

    def paper_draw(cv):
        ctx = cv.ctx
        x, y, w, h = paper_box
        cv.shape_shadow(box_pts(x, y, w, h), dx=5, dy=9, blur=16, color=(60, 40, 20, 0.2))
        paths.draw(cv, box_pts(x, y, w, h), PAPER_SCRAP, fill=True)
        ctx.save()
        ctx.translate(paper_box.cx, y - 4)
        ctx.rotate(0.03)
        ctx.rectangle(-60, -17, 120, 34)
        ctx.set_source_rgba(*TAPE)
        ctx.fill()
        ctx.restore()

    def write(words, fnt, x, y, alpha=1.0):
        marks.append(('text', words, fnt, x, y, alpha))

    b = parts['badge']
    marks.append(('stroke', Stroke(box_pts(*b), seed_of('page badge'), passes=2, width=2.8 * u, closed=True,
                                   overshoot=0)))
    write(BADGE, F['prop'], b.cx - text.measure(BADGE, F['prop']) / 2, b.y + 0.15 * F['prop'].size)
    write(CARD.number, F['num'], b.cx - text.measure(CARD.number, F['num']) / 2,
          b.y + text.line_height(F['prop']) * 0.8)
    flows = {fl.field: fl for fl in parts['flows']}
    for run in flows['title'].runs:
        write(*run)
    labels = iter(parts['labels'])
    write(*next(labels), alpha=0.8)  # SUMMARY
    for run in flows['origin'].runs:
        write(*run, alpha=0.85)
    shapes = iter(parts['shapes'])
    kind, (x, y, w) = next(shapes)
    marks.append(('stroke', Stroke([(x, y), (x + w, y)], seed_of('page rule', 0), passes=2, width=2 * u,
                                   overshoot=2, alpha=0.6)))
    for run in flows['summary'].runs:
        write(*run)
    if 'fiscal' in flows:
        write(*next(labels))  # the fiscal statement's heading
        for run in flows['fiscal'].runs:
            write(*run)
    if 'yes' not in flows:
        return paper_draw, marks
    write(*next(labels), alpha=0.8)  # WHAT YOUR VOTE MEANS
    kind, (x, y, w) = next(shapes)
    marks.append(('stroke', Stroke([(x, y), (x + w, y)], seed_of('page rule', 1), passes=2, width=2 * u,
                                   overshoot=2, alpha=0.6)))
    # the YES and NO boxes: the same outline, lettering and timing
    for key in ('yes', 'no'):
        kind, (x, y, w, h) = next(shapes)
        marks.append(('stroke', Stroke(box_pts(x, y, w, h), seed_of('page vote box'), passes=2, width=2.6 * u,
                                       closed=True, overshoot=0, alpha=0.75)))
        write(*next(labels))
        for run in flows[key].runs:
            write(*run)
    return paper_draw, marks


def page_items(paper_box, parts, L, f0, budget, whole):
    """The page's items from frame f0: drawn on within `budget` frames, or,
    if `whole`, already drawn (the page coming back)."""
    paper_draw, marks = page_static(paper_box, parts, L)
    items = []
    f = f0
    if whole:
        f0 = f = f0 - 2
    items.append(fade_item(f, f + 6, paper_draw))
    f += 4
    for m in marks:
        if m[0] == 'stroke':
            st = m[1]
            d = max(6, paths.length(st.passes[0][0]) / 120)
            items.append(stroke_item(f, f + d, st, pencil=not whole))
            f += d
        else:
            _, words, fnt, x, y, alpha = m
            d = write_frames(text.measure(words, fnt))
            items.append(text_item(f, f + d, words, fnt, x, y, alpha=alpha, pencil=not whole))
            f += d
    if whole:
        for it in items:
            it.f0, it.f1 = f0, f0 + 1
        return items
    return scaled(items, f0, budget)


def _clamp(v, lo, hi):
    """v within lo..hi; their midpoint if the range is empty."""
    return (lo + hi) / 2 if lo > hi else min(max(v, lo), hi)


class Camera:
    """Where the stage looks on the page at frame n: identity until f0, then
    easing over ZOOM frames to frame `target` (a Box on the page) whole, at
    most PAGE_ZOOM_MAX times larger, never past the paper's edge."""

    def __init__(self, stage, paper_box, target=None, f0=None, f1=None):
        self.stage, self.paper, self.f0, self.f1 = stage, paper_box, f0, f1
        self.k, self.c = 1.0, (stage.cx, stage.cy)
        if target is not None:
            k = min(stage.w * 0.9 / target.w, stage.h * 0.7 / target.h, PAGE_ZOOM_MAX)
            k = max(1.0, k)
            hw, hh = stage.w / 2 / k, stage.h / 2 / k
            cx = _clamp(target.cx, paper_box.x + hw, paper_box.right - hw)
            cy = _clamp(target.cy, paper_box.y + hh, paper_box.bottom - hh)
            self.k, self.c = k, (cx, cy)

    def at(self, n):
        if self.f0 is None or n <= self.f0:
            return 1.0, (self.stage.cx, self.stage.cy)
        e = CAMERA(vb.clamp01((n - self.f0) / (self.f1 - self.f0)))
        # the scale eases geometrically, so the zoom feels even
        k = self.k ** e
        q = (k - 1) / (self.k - 1) if self.k > 1 else e
        sx, sy = self.stage.cx, self.stage.cy
        return k, (sx + (self.c[0] - sx) * q, sy + (self.c[1] - sy) * q)

    def apply(self, cv, n):
        k, (cx, cy) = self.at(n)
        ctx = cv.ctx
        ctx.translate(self.stage.cx, self.stage.cy)
        ctx.scale(k, k)
        ctx.translate(-cx, -cy)


def _union(boxes):
    x0 = min(b.x for b in boxes)
    y0 = min(b.y for b in boxes)
    x1 = max(b.right for b in boxes)
    y1 = max(b.bottom for b in boxes)
    return Box(x0, y0, x1 - x0, y1 - y0)


# ---- highlights: phrases on the page, marked with a highlighter ----
SWEEP = 15         # frames one occurrence of a phrase takes to sweep on (0.5 s)
# The highlighter's ink: one yellow for every mark on the card, never the
# headings' orange (rule 7.4), multiplied onto the paper so the words over it
# stay dark and crisp. Its alpha leaves the band clearly darker than the paper
# in greyscale too, so it reads without colour.
HIGHLIGHTER = (255, 221, 48)
BAND_ALPHA = 0.75
FAINT = 0.3        # a band, as a page comes back with its clicked terms


def _norm(words):
    """`words` lower-cased with its punctuation dropped, for finding a phrase
    in a line's narration: (text, offsets of each kept character)."""
    import re
    out, at = [], []
    for m in re.finditer(r"[\w']+", words.lower()):
        if out:
            out.append(' ')
            at.append(m.start())
        out.extend(m.group(0))
        at.extend(range(m.start(), m.end()))
    return ''.join(out), at


def highlight_starts(beat, phrases):
    """The frame each of a line's highlight `phrases` starts sweeping on: at
    its estimated spoken position (narration is timed per line, not per
    word): where the phrase's words occur in the line's text, that
    character offset's fraction of the line's spoken span; otherwise the
    k-th of n phrases at k/n of it (docs/SCRIPT-FORMAT.md)."""
    a, b = SPOKEN.get((beat.section, beat.index), (beat.start, beat.end))
    said, _ = _norm(beat.line.text)
    out = []
    for k, phrase in enumerate(phrases):
        at = said.find(_norm(phrase)[0])
        frac = at / max(1, len(said)) if at >= 0 else k / len(phrases)
        out.append(a + (b - a) * frac)
    return out


class Band:
    """A highlighter band laid behind a phrase's words, one a line (its
    `boxes`), swept on left to right, box after box: a translucent yellow
    multiplied onto the paper, so the lettering over it stays as dark as
    before. A chisel tip's mark: its ends cut flat at a slant, its ink a
    little uneven along the stroke and a touch heavier at its edges, and at
    its last box the tip going back over the end, which lays the ink twice
    there, a shade darker."""

    def __init__(self, boxes, u, seed, alpha=BAND_ALPHA):
        rnd = random.Random(seed)
        self.alpha = alpha
        self.segs = []
        for i, b in enumerate(boxes):
            x0 = b.x - rnd.uniform(3, 6) * u
            x1 = b.right + rnd.uniform(3, 6) * u
            yc = b.y + b.h * 0.56 + rnd.uniform(-0.6, 0.6) * u
            hh = b.h * 0.3
            lean = hh * 0.55  # the chisel's slant: its ends' tops a little ahead
            rise = rnd.uniform(-1.2, 1.2) * u  # the stroke not quite level
            # the density along the stroke: a few soft stops, heavier where the nib lands
            n = max(2, int((x1 - x0) / (40 * u)))
            dens = [1.0] + [rnd.uniform(0.84, 0.98) for _ in range(n)]
            back = min((x1 - x0) * 0.3, 70 * u) if i == len(boxes) - 1 else 0
            self.segs.append(dict(x0=x0, x1=x1, yc=yc, hh=hh, lean=lean, rise=rise, dens=dens, back=back,
                                  dy=rnd.uniform(-0.12, 0.12) * hh))
        self.total = sum(s['x1'] - s['x0'] + s['back'] for s in self.segs) or 1

    @staticmethod
    def _quad(s, xa, xb, dy=0.0):
        """The band from xa to xb (its centre line), its ends cut at the
        chisel's slant."""
        x0, x1, yc, hh, lean, rise = s['x0'], s['x1'], s['yc'] + dy, s['hh'], s['lean'], s['rise']

        def y(x):
            return yc + rise * ((x - x0) / max(1, x1 - x0) - 0.5)
        return [(xa + lean, y(xa) - hh), (xb + lean, y(xb) - hh), (xb - lean, y(xb) + hh), (xa - lean, y(xa) + hh)]

    def _lay(self, ctx, s, quad, k=1.0):
        """Fill `quad` with the band's ink: multiplied, a little uneven."""
        x0, x1 = s['x0'], s['x1']
        r, g, b = (c / 255 for c in HIGHLIGHTER)
        grad = cairo.LinearGradient(x0, 0, x1, 0)
        for j, d in enumerate(s['dens']):
            grad.add_color_stop_rgba(j / (len(s['dens']) - 1), r, g, b, self.alpha * k * d)
        sp._poly(ctx, quad)
        ctx.set_source(grad)
        ctx.fill()
        # the felt's edges carry a little more ink than its middle
        ctx.set_line_width(max(1.0, s['hh'] * 0.08))
        ctx.set_source_rgba(r, g, b, self.alpha * k * 0.35)
        for a, z in ((0, 1), (3, 2)):
            ctx.move_to(*quad[a])
            ctx.line_to(*quad[z])
            ctx.stroke()

    def draw(self, cv, p):
        ctx = cv.ctx
        left = p * self.total
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_MULTIPLY)
        for s in self.segs:
            if left <= 0:
                break
            x0, x1, back = s['x0'], s['x1'], s['back']
            if left < x1 - x0:
                # sweeping: the band so far, its leading end cut at the chisel's slant
                self._lay(ctx, s, self._quad(s, x0, x0 + left))
            else:
                self._lay(ctx, s, self._quad(s, x0, x1))
                if back and left > x1 - x0:
                    # the nib going back over the end: the ink laid twice
                    xb = x1 - min(back, left - (x1 - x0))
                    self._lay(ctx, s, self._quad(s, xb, x1, s['dy']), 0.55)
            left -= x1 - x0 + back
        ctx.restore()

    def head(self, p):
        """The nib's middle: at the band's leading end, or coming back over it."""
        left = p * self.total
        for s in self.segs:
            run = s['x1'] - s['x0']
            if left <= run:
                return s['x0'] + left, s['yc']
            if left <= run + s['back']:
                return s['x1'] - (left - run), s['yc'] + s['dy']
            left -= run + s['back']
        s = self.segs[-1]
        return s['x1'] - s['back'], s['yc'] + s['dy']


def band_item(f0, f1, occ, u, alpha=BAND_ALPHA, tool=True):
    """One occurrence `occ` (its boxes) of a phrase highlighted over f0..f1,
    the highlighter on it (unless not `tool`). Every band has the same
    seed, so a hand's unevenness never tells the YES box's marks from the
    NO box's (rule 7.4)."""
    band = Band(occ, u, seed_of('band'), alpha)
    return Item(f0, f1, band.draw, band.head if tool else None, HIGHLIGHTER, tool='highlighter')


def highlight_items(parts, beat, ready, u):
    """The bands for a line's `highlight` phrases: each starting at its
    estimated spoken position (no earlier than frame `ready`, when the page
    is up), its occurrences swept on one after another, alike."""
    phrases = beat.line.visual.highlight
    items = []
    f = ready
    for phrase, at in zip(phrases, highlight_starts(beat, phrases)):
        f = max(f, at)
        for occ in focus_boxes(parts, phrase):
            items.append(band_item(f, f + SWEEP, occ, u))
            f += SWEEP
    return items


def page_run(runs, L, first_f, fmt, state):
    """The page for a run of consecutive `page` lines and the lines they stay
    up for, one continuous page (`runs`: the runs_of entries, in order):
    drawn on the first time, faded back in (with every term clicked so far
    ticked off) after that; then each `page` line, as it is narrated, adds
    its highlights or its click: the term highlighted, and, with a single
    click in the run, zoomed in on. `state` carries what earlier page runs did:
    whether the page was drawn, and the terms clicked. Returns (items,
    marks, camera, fade-in frame or None)."""
    stage = L['page_stage']
    u = L['u']
    paper_box, parts = page_plan(fmt)
    first = not state['drawn']
    room = runs[0][2][-1].end - first_f
    if first:
        items = page_items(paper_box, parts, L, first_f, min(PAGE_DRAW, room * 0.35), whole=False)
        f = max(it.f1 for it in items) + 4
        fade_in = None
    else:
        items = page_items(paper_box, parts, L, first_f, 0, whole=True)
        f = first_f + FADE
        fade_in = first_f
    state['drawn'] = True
    bands = []  # laid behind the lettering
    # the terms clicked before this run: each highlighted, faint, with a tick
    for focus in state['clicked']:
        for occ in focus_boxes(parts, focus):
            bands.append(band_item(first_f - 2, first_f - 1, occ, u, BAND_ALPHA * FAINT, tool=False))
            tick = _tick(occ[0], u, seed_of('tick', focus))
            items.append(stroke_item(first_f - 2, first_f - 1, tick, alpha=0.8, pencil=False))
    camera = Camera(stage, paper_box)
    cameras = []
    for r, (_, chart, lines) in enumerate(runs):
        run_f0 = first_f if r == 0 else lines[0].start
        if r:
            f = max(f, run_f0 + 2)
        v = chart.visual
        if v.highlight:
            hi = highlight_items(parts, lines[0], f, u)
            bands += hi
            f = max([f] + [it.f1 for it in hi])
        if v.focus:
            focus = v.focus
            occs = focus_boxes(parts, focus)
            boxes = [b for occ in occs for b in occ]
            room = lines[-1].end - run_f0
            k = min(1.0, (room * 0.6 - (f - run_f0)) / (CLICK + ZOOM + 4)) if room > 0 else 1.0
            k = max(k, 0.4)
            # one sweep over every occurrence, at the highlighter's one pace
            length = sum(b.w for b in boxes)
            for occ in occs:
                d = CLICK * k * sum(b.w for b in occ) / length
                bands.append(band_item(f, f + d, occ, u))
                f += d
            z0 = f + 3
            # frame the highlights whole, not just the words in them
            t = _union(boxes)
            mx, my = 24 * u, 16 * u
            cam = Camera(stage, paper_box, Box(t.x - mx, t.y - my, t.w + 2 * mx, t.h + 2 * my), z0, z0 + ZOOM * k)
            cameras.append(cam)
    for _, chart, _ in runs:
        focus = chart.visual.focus
        if focus and focus not in state['clicked']:
            state['clicked'].append(focus)
    # One click holds the camera on it; several in one run keep the page whole
    # (PAGE_ZOOM_MAX is 1 in any case: the page is readable whole).
    if len(cameras) == 1:
        camera = cameras[0]
    items = items[:1] + bands + items[1:]  # the paper first, then the bands under the words
    marks = [Mark('chart', paper_box)]
    return items, marks, camera, fade_in


class PageGroup(Group):
    """A Group for the page: drawn through its camera, clipped to the stage,
    and faded in from `fade_in` (None: drawn on instead)."""

    def __init__(self, items, marks, f0, out, camera, fade_in):
        super().__init__(items, marks, f0, out)
        self.camera, self.fade_in = camera, fade_in

    def draw(self, cv, n):
        if n < self.f0 - 1 or (self.out is not None and n >= self.out + FADE):
            return
        opacity = 1.0
        if self.fade_in is not None:
            opacity = vb.clamp01((n - self.fade_in) / FADE)
        if self.out is not None and n >= self.out:
            opacity = min(opacity, 1 - (n - self.out) / FADE)
        if opacity <= 0:
            return
        s = self.camera.stage
        ctx = cv.ctx
        # the zoomed page shows only within the stage; at full view, its shadow too
        grow = 0 if self.camera.at(n)[0] > 1.0001 else 40
        with cv.clip(s.x - grow, s.y - grow, s.w + 2 * grow, s.h + 2 * grow):
            with cv.layer(opacity=opacity):
                ctx.save()
                self.camera.apply(cv, n)
                for it in self.items:
                    it.draw(cv, n)
                ctx.restore()
        if opacity >= 1:
            for m in self.marks:
                if n >= m.f0:
                    cv.mark(m.name, *m.box)


def is_page(run):
    return run[0] == 'chart' and run[1].visual.kind == 'page'


def page_spans():
    """The stretches of the film in the full-page view, (start, end) frames:
    from a page run's first line to its last, runs back to back joined."""
    spans = []
    for sec in BOARD.sections:
        for run in runs_of(sec):
            if not is_page(run):
                continue
            a, b = run[2][0].start, run[2][-1].end
            if spans and a <= spans[-1][1] + 1:
                spans[-1] = (spans[-1][0], b)
            else:
                spans.append((a, b))
    return spans


PAGE_SPANS = page_spans()


def page_view(n):
    """How far frame n is in the full-page view, 0..1: it fades in over FADE
    frames as a page run starts, and out over FADE as it ends, alongside the
    visuals' own fades."""
    for a, b in PAGE_SPANS:
        if a <= n < b + FADE:
            return min(vb.clamp01((n - a) / FADE), 1 - vb.clamp01((n - b) / FADE))
    return 0.0


def build(fmt):
    L = LAYOUTS[fmt]
    groups = []
    slides = []  # (frame the ring starts refilling, frame it is empty): one per picture on the stage
    pages = dict(drawn=False, clicked=[])  # what earlier `page` lines did
    pending = []  # consecutive `page` runs, one continuous page: [(run, first_f)]

    def flush():
        if not pending:
            return
        runs = [r for r, _ in pending]
        first_f = pending[0][1]
        start, end = runs[0][2][0].start, runs[-1][2][-1].end
        items, marks, camera, fade_in = page_run(runs, L, first_f, fmt, pages)
        for m in marks:
            m.f0 = first_f
        groups.append(PageGroup(items, marks, start, end, camera, fade_in))
        slides.append((max(start, first_f - FADE), end))
        pending.clear()

    side_secs = [sb for sb in BOARD.sections if sb.section.side is not None]

    for sec in BOARD.sections:
        if sec.section.side is not None:
            # both sides live on one slide (STANDARD.md rule 2.2): built
            # once, when the first one begins, and held through the second
            if side_secs and sec is side_secs[0]:
                flush()
                side_a, side_b = side_secs
                h_f0 = side_a.start + (FADE if side_a.number else 4)
                items, marks = sides_group(side_a, side_b, L, fmt, h_f0)
                groups.append(Group(items, marks, side_a.start, side_b.end))
                slides.append((max(side_a.start, h_f0 - FADE), side_b.end))
            continue
        runs = runs_of(sec)
        h_f0 = sec.start + (FADE if sec.number else 4)
        h_items, h_end, h_box = heading_items(sec, L, h_f0)
        opens_on_page = bool(runs) and is_page(runs[0]) and runs[0][1].index == 0
        if opens_on_page:
            # The section opens in the full-page view: its heading is not
            # written on, but fades in whole when a later visual leaves the view.
            for it in h_items:
                it.f0, it.f1, it._head = h_f0 + FADE, h_f0 + FADE + 1, None
            h_end = h_f0 - 2
        else:
            flush()  # the stage clears between the sections
        groups.append(Group(h_items, [Mark('heading', h_box, sec.start)], sec.start, sec.end, hidden=page_view))
        for k, run in enumerate(runs):
            kind, chart, lines = run
            start = lines[0].start
            first_f = max(h_end + 2, start + (FADE if start > sec.start else 0))
            end = lines[-1].end
            if is_page(run):
                # a page carries on from a page just before it, even across a
                # section's start: it stays up, and adds its highlights or click
                pending.append((run, first_f))
                continue
            flush()
            if kind == 'chart':
                items, marks = chart_run(chart, lines, L, first_f)
            else:
                items, marks = ballot_run(lines, L, first_f)
            for m in marks:
                m.f0 = first_f
            groups.append(Group(items, marks, start, end))
            slides.append((max(start, first_f - FADE), end))
    flush()
    # the closing sources card: never fades
    card_items, card_marks = sources_card(L, BOARD.narration_end + 8)
    groups.append(Group(card_items, card_marks, BOARD.narration_end))
    items = [it for g in groups for it in g.items]
    schedule = sorted((it for it in items if it._head), key=lambda it: it.f0)
    return dict(L=L, groups=groups, schedule=schedule, captions=caption_chunks(L), slides=sorted(slides))


SOURCES_GAP = 0.45  # the least gap between two sources, as a share of the list's line height


def sources_card(L, f0):
    """The closing card: 'Sources' as a heading, and every cited source,
    numbered, in a list that fills the page from under the heading down to
    the bottom of where the caption would be (the card has none), as the
    sides slide's cards do: its height goes to the type first, the largest
    (up to L['sources_font']) at which the list fits with the sources at
    their least gap; what is left is shared out evenly between the gaps
    between the sources and the room above and below the list."""
    hb = L['heading']
    u = L['u']
    fnt = L['heading_font']
    items, f, hbox = write_lines(f0, ['Sources'], fnt, hb.x, hb.y + 6, align='center', width=hb.w)
    w = text.measure('Sources', fnt)
    under = Stroke([(hb.cx - w / 2 - 6, hbox.bottom + 2), (hb.cx + w / 2 + 8, hbox.bottom + 4)],
                   seed_of('underline'), passes=2, width=5 * u)
    items.append(stroke_item(f + 1, f + 9, under, ORANGE))
    f += 10
    box = sources_room(L, hbox)
    n = len(BOARD.cited)
    sf = L['sources_font']
    while True:
        num_w = text.measure(f'{n}.', sf) + 0.4 * sf.size
        blocks = [text.wrap(s.publisher, sf, box.w - num_w, balance=True) for s in BOARD.cited]
        lh = text.line_height(sf)
        gap = lh * SOURCES_GAP
        total = sum(len(b) * lh for b in blocks) + gap * (n - 1)
        if total <= box.h or sf.size < 22:
            break
        sf = font(sf.size * 0.97, family=PRINT)
    share = max(0, box.h - total) / (n + 1)
    gap += share
    y = box.y + share
    top = y
    for i, lines in enumerate(blocks):
        ni, _, _ = write_lines(f, [f'{i + 1}.'], sf, box.x, y, speed=2)
        items += ni
        li, f, _ = write_lines(f + 2, lines, sf, box.x + num_w, y, speed=2.2)
        items += li
        y += len(lines) * lh + gap
        f += 3
    return items, [Mark('heading', hbox), Mark('sources', Box(box.x, top, box.w, y - gap - top))]


def sources_room(L, hbox):
    """The room the sources list fills: the stage's width, from EDGE_GAP
    under the heading's underline down to the bottom of the caption's scrap."""
    st = L['stage']
    y = hbox.bottom + 4 + EDGE_GAP * L['u']
    return Box(st.x, y, st.w, L['scrap'].bottom - y)


# ---- captions: the current phrase on a taped scrap, fully legible ----
def caption_chunks(L):
    """Each phrase cut into chunks of at most `caption_lines` lines, each
    shown from its first word until the next chunk (or a moment after the
    phrase, before a long pause). Only the words being spoken are shown:
    never a ghost of what comes next."""
    scrap = L['scrap']
    fnt = L['caption_font']
    width = scrap.w - 80
    maxl = L['caption_lines']
    words = list(TRACK)
    wi = 0
    out = []
    phrases = PHRASES
    for pi, ph in enumerate(phrases):
        tokens = ph.text.split()
        mine = words[wi:wi + len(tokens)]
        wi += len(tokens)
        if len(mine) != len(tokens):
            mine = None
        lines = text.wrap(ph.text, fnt, width, balance=False)
        groups = [lines[i:i + maxl] for i in range(0, len(lines), maxl)]
        # balance the chunks' word counts, so the last isn't a stray word
        counts = [sum(len(ln.split()) for ln in g) for g in groups]
        if len(groups) > 1:
            per = math.ceil(len(tokens) / len(groups))
            counts = [per] * (len(groups) - 1)
            counts.append(len(tokens) - sum(counts))
            ok = all(len(text.wrap(' '.join(tokens[sum(counts[:k]):sum(counts[:k + 1])]), fnt, width,
                                   balance=True)) <= maxl for k in range(len(counts)))
            if not ok:
                counts = [sum(len(ln.split()) for ln in g) for g in groups]
        nxt = phrases[pi + 1].start if pi + 1 < len(phrases) else VOICE_SECONDS + 0.5
        end = min(nxt - 0.05, ph.end + 0.8)
        k0 = 0
        chunks = []
        for c in counts:
            chunk_words = tokens[k0:k0 + c]
            if mine:
                t0 = mine[k0].start
            else:
                t0 = ph.start + (ph.end - ph.start) * k0 / len(tokens)
            chunks.append(dict(start=t0, lines=text.wrap(' '.join(chunk_words), fnt, width, balance=True)))
            k0 += c
        chunks[0]['start'] = ph.start - 0.1
        for a, b in zip(chunks, chunks[1:]):
            a['end'] = b['start']
        chunks[-1]['end'] = end
        out += chunks
    return out


_SCRAPS = {}


def scrap_edge(s):
    key = tuple(s)
    if key not in _SCRAPS:
        _SCRAPS[key] = paths.torn([(s.x, s.y), (s.right, s.y + 4), (s.right - 3, s.bottom), (s.x + 2, s.bottom - 3)],
                                  seed=91, amount=5, step=3)
    return _SCRAPS[key]


def draw_captions(cv, n, P, s, mark=True):
    """The caption scrap, at box `s`: the normal layout's, or the full-page
    view's."""
    L = P['L']
    t = n / FPS
    ctx = cv.ctx
    edge = scrap_edge(s)
    cv.shape_shadow(edge, dx=6, dy=10, blur=18, color=(60, 40, 20, 0.22))
    paths.draw(cv, edge, PAPER_SCRAP, fill=True)
    for x, y, a in ((s.x + 40, s.y - 6, -0.5), (s.right - 40, s.y - 2, 0.45)):
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(a)
        ctx.rectangle(-55, -18, 110, 36)
        ctx.set_source_rgba(*TAPE)
        ctx.fill()
        ctx.restore()
    ch = next((c for c in P['captions'] if c['start'] <= t < c['end']), None)
    if ch is None:
        return
    fnt = L['caption_font']
    lines = ch['lines']
    lh = text.line_height(fnt)
    y0 = s.cy - lh * len(lines) / 2 + 2
    fade = vb.clamp01((t - ch['start']) / 0.08)
    sp.pencil_text(cv, lines, fnt, s.x, y0, GRAPHITE, fade, align='center', width=s.w)
    if mark:
        cv.mark('caption', s.x, s.y, s.w, s.h)


# ---- the running header: the measure's title, on every page ----
HEADER_ALPHA = 0.8  # quieter than the heading, but dark enough to read on a phone
HEADER_LINES = 2


@functools.lru_cache(maxsize=None)
def header_fit(title, band, size):
    """The running title set to fill `band`: the largest font, from `size`
    down, at which it takes at most HEADER_LINES lines across the band's
    width and they fit its height. Returns (font, lines, top y), the lines
    centred in the band's height."""
    fnt = font(size, family=PRINT)
    while True:
        lines = text.wrap(title, fnt, band.w, balance=True)
        h = text.line_height(fnt) * len(lines)
        fits = len(lines) <= HEADER_LINES and h <= band.h
        if fits or fnt.size < 12:
            return fnt, lines, band.y + max(0, (band.h - h) / 2)
        fnt = font(fnt.size * 0.97, family=PRINT)


def draw_header(cv, L, alpha=1.0):
    """The running title, at `alpha`: it fades out in the full-page view."""
    hb = L['header']
    fnt, lines, y = header_fit(CONTEST.title, hb, L['header_font'].size)
    drawn = sp.pencil_text(cv, lines, fnt, hb.x, y, GRAPHITE, HEADER_ALPHA * alpha, align='center', width=hb.w)
    if alpha >= 1:
        cv.mark('header', *drawn)


# ---- the footer: how to report a bias, on every frame (rule 5.1) ----
FOOTER = 'ballotreels · bias is a bug · report it at github.com/mgalgs/ballotreels'


def draw_footer(cv, L, fb, alpha=1.0):
    """One quiet line under the caption, the same on every frame: never the
    accent colour, and clear of the caption scrap and any source line. `fb`
    is its box: the normal layout's, or the full-page view's."""
    fnt = L['footer_font']
    while text.measure(FOOTER, fnt) > fb.w and fnt.size > 14:
        fnt = font(fnt.size * 0.95, family=PRINT)
    drawn = sp.pencil_text(cv, [FOOTER], fnt, fb.x, fb.y, GRAPHITE, 0.62 * alpha, align='center', width=fb.w)
    if alpha >= 1:
        cv.mark('footer', *drawn)


# ---- the countdown ring: how long until the picture changes ----
RING_ALPHA = 0.62   # the footer's quiet graphite, never the accent colour
RING_TRACK = 0.16   # the empty ring, faint


def ring_at(n, slides):
    """(fill 0..1, opacity 0..1) of the countdown ring at frame n, or None
    when the stage is empty. Each picture on the stage, (a, b) in `slides`,
    refills it over FADE frames from a, and it then empties steadily to
    nothing at b, when the picture starts to go. It fades in with a picture
    that follows an empty stage, and out, empty, when the stage clears."""
    for i, (a, b) in enumerate(slides):
        if a <= n < b:
            full = min(b, a + FADE)
            if n < full:
                fill = (n - a) / FADE
            else:
                fill = 1 - (n - full) / max(1, b - full)
            follows = i > 0 and a - slides[i - 1][1] <= 1
            return fill, 1.0 if follows else vb.clamp01((n - a) / FADE)
    for a, b in slides:
        if b <= n < b + FADE:
            return 0.0, 1 - (n - b) / FADE
    return None


@functools.lru_cache(maxsize=8)
def _ring_path(cx, cy, r):
    """The ring as a hand draws it, from the top counter-clockwise round to
    the top again: a polyline with a slight seeded wobble."""
    rnd = random.Random(seed_of('countdown', cx, cy))
    ph = rnd.uniform(0, 6.3)
    n = 96
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 - 2 * math.pi * i / n
        rr = r * (1 + 0.025 * math.sin(3 * a + ph))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def draw_ring(cv, ring, fill, alpha):
    """The countdown ring at (cx, cy, r): the part still to run, from the
    top round clockwise to `fill` of the way, over a faint full ring."""
    cx, cy, r = ring
    if alpha <= 0:
        return
    ctx = cv.ctx
    pts = _ring_path(cx, cy, r)
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    w = r * 0.2
    ctx.new_path()
    sp._path(ctx, pts)
    ctx.set_line_width(w)
    ctx.set_source(sp.ink(GRAPHITE, RING_TRACK * alpha))
    ctx.stroke()
    if fill > 0.002:
        # the stroke runs counter-clockwise from the top: revealing `fill`
        # of it leaves the gap opening clockwise from the top
        shown = paths.reveal(pts, min(1.0, fill))
        if len(shown) >= 2:
            ctx.new_path()
            sp._path(ctx, shown)
            ctx.set_line_width(w)
            ctx.set_source(sp.ink(GRAPHITE, RING_ALPHA * alpha))
            ctx.stroke()
    ctx.restore()
    if alpha >= 1:
        cv.mark('ring', cx - r - w, cy - r - w, 2 * (r + w), 2 * (r + w))


# ---- the pencil, or the highlighter: only while something is being drawn ----
LIFT = 46   # px a fading tool lifts along its own resting angle, so it visibly leaves


def _lift(x, y, t):
    """(x, y) nudged `t` (0..1) of the way off the page along the tool's own
    resting angle (sketch.RESTING_ANGLE, the pencil and highlighter body's
    own tilt), so a fade out reads as the tool lifting away rather than
    hovering in place over a finished mark."""
    return x + LIFT * t * math.cos(RESTING_ANGLE), y + LIFT * t * math.sin(RESTING_ANGLE)


def pencil_at(n, P):
    """(x, y, ink, tool, alpha) of the pencil (or highlighter) tip at frame
    n, or None. It follows whatever is being drawn; across a short gap
    between two marks by the same tool it moves straight from one to the
    next, and otherwise it lifts off and fades out where it stopped (and
    in where it starts, the same way in reverse). It never travels or
    idles, and it never sits still, fully drawn, over a finished mark."""
    prev = nxt = None
    for it in P['schedule']:
        if it.f0 <= n <= it.f1:
            x, y = it.head(n)
            return x, y, it.ink, it.tool, 1.0
        if it.f1 < n:
            if prev is None or it.f1 > prev.f1:
                prev = it
        elif it.f0 > n:
            nxt = it
            break
    fa = prev.f1 if prev else -1e9
    fb = nxt.f0 if nxt else 1e9
    if fb - fa <= BRIDGE and prev.tool == nxt.tool:
        a, b = prev.head(fa), nxt.head(fb)
        q = DRAW(vb.clamp01((n - fa) / (fb - fa)))
        return a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q, nxt.ink, nxt.tool, 1.0
    if n - fa < PENCIL_FADE:
        t = (n - fa) / PENCIL_FADE
        x, y = _lift(*prev.head(fa), t)
        return x, y, prev.ink, prev.tool, 1 - t
    if fb - n < PENCIL_FADE:
        t = (fb - n) / PENCIL_FADE
        x, y = _lift(*nxt.head(fb), t)
        return x, y, nxt.ink, nxt.tool, 1 - t
    return None


def draw_pencil(cv, n, P):
    at = pencil_at(n, P)
    if not at:
        return
    x, y, ink, tool, alpha = at
    if tool == 'highlighter':
        def sprite():
            sp.draw_highlighter(cv, x, y, ink)
    else:
        def sprite():
            sp.draw_pencil(cv, x, y, None if ink == GRAPHITE else ink)
    if alpha >= 1:
        sprite()
        return
    with cv.layer(opacity=alpha):
        sprite()


# ---- the frame ----
PLANS = {fmt: build(fmt) for fmt in LAYOUTS}


def draw(n, cv):
    P = PLANS[cv.format.name]
    ctx = cv.ctx
    ctx.set_source_surface(sp.backdrop(cv.width, cv.height), 0, 0)
    ctx.paint()
    L = P['L']
    v = page_view(n)
    # The full-page view: the running title fades out, and the caption and
    # footer cross-fade to their places at the page's bottom, where they
    # already are in 9:16.
    if v < 1:
        draw_header(cv, L, 1 - v)
    for fb, a in ((L['footer'], 1 - v), (L['page_footer'], v)):
        if L['footer'] == L['page_footer']:
            draw_footer(cv, L, fb)
            break
        if a > 0:
            draw_footer(cv, L, fb, a)
    for g in P['groups']:
        g.draw(cv, n)
    ring = ring_at(n, P['slides'])
    if ring is not None:
        fill, alpha = ring
        for at, a in ((L['ring'], 1 - v), (L['page_ring'], v)):
            if L['ring'] == L['page_ring']:
                draw_ring(cv, at, fill, alpha)
                break
            if a > 0:
                draw_ring(cv, at, fill, alpha * a)
    draw_pencil(cv, n, P)
    if n < BOARD.narration_end:
        for s, a in ((L['scrap'], 1 - v), (L['page_scrap'], v)):
            if L['scrap'] == L['page_scrap']:
                draw_captions(cv, n, P, s)
                break
            if a >= 1:
                draw_captions(cv, n, P, s)
            elif a > 0:
                with cv.layer(opacity=a):
                    draw_captions(cv, n, P, s, mark=False)


SEGMENTS = [vb.Segment(s.label, s.start, s.end,
                       data={'copy': [s.section.heading] + [b.line.text for b in s.lines]})
            for s in BOARD.sections]
SEGMENTS.append(vb.Segment('sources', BOARD.narration_end, BOARD.end,
                           data={'copy': ['Sources'] + [s.publisher for s in BOARD.cited]}))
TIMELINE = vb.Timeline(GRID, SEGMENTS, end=BOARD.end)

# The drawing sounds follow the 9x16 schedule: the two formats' choreography
# differs by at most a few frames (their layouts scale the same text, so
# time differently by width), and the film has one shared audio track for
# every format, as the narration already does.
DRAW_SOUND = dsnd.sound_for(PLANS['9x16']['schedule'], FPS, BOARD.end,
                            voice_rms=dsnd.narration_rms(VOICE.path))


def voice_sounds():
    """VOICE as one `vb.Sound`, or, when a side needs padding (PAD), as two:
    the narration up to the pad point, a silent gap of PAD.seconds, then the
    rest of the narration — so the audio actually played carries the same
    pad the picture does (storyboard.layout), to the frame."""
    if PAD is None:
        return (VOICE.sound(at=0, fps=FPS),)
    at = to_frame(PAD.at, FPS)
    gap = to_frame(PAD.seconds, FPS)
    total = VOICE.frames(FPS)
    return (
        vb.Sound(path=VOICE.path, at=0, start=0.0, frames=at,
                 fade_in_frames=0, fade_out_frames=3),
        vb.Sound(path=VOICE.path, at=at + gap, start=PAD.at, frames=total - at,
                 fade_in_frames=3, fade_out_frames=0),
    )


FILM = vb.Film(
    draw=draw,
    timeline=TIMELINE,
    formats=('9x16', '16x9'),
    background='#f2ebd8',
    sounds=(*voice_sounds(), DRAW_SOUND),
)

if __name__ == '__main__':
    vb.main(__file__)
