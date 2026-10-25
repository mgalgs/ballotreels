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
only (never a value, rule 7.4), Caveat for labels and Patrick Hand for
captions and notes, captions on a taped paper scrap.

The motion is calm. Each section is a page: its heading, written and
underlined, and a stage below it. A visual draws on once, in about a
second, with a pencil that is on the page only while something is being
drawn, and then holds still; it stays up through the lines after it until
a later line in the section brings its own (the old one fades out) or the
section ends (the whole page fades out, and the next heading draws on).
The stage shows
- the line's visual, if it has one (a chart, a number, a timeline, a
  phrase of the line's words or a named figure), with "Source: ..." under
  it for as long as it is up (rule 7.1);
- in the `what` and `vote` sections, before any visual, the ballot: the
  measure's title and its two options, drawn alike;
- otherwise nothing: an empty page under the heading.
The two sides get the same page whichever plays first (rules 2.2, 4.1);
their pages are built by the same code from line positions, never from the
side. The film closes on a card listing every cited source (rule 1.5).
No music and no sound effects: the narration is the only sound.

Time is in frames: one frame a beat, since cuts follow the narration, not
a music grid.
"""
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

import videobuilder as vb  # noqa: E402
from videobuilder import Box, paths, text  # noqa: E402

import sketch as sp  # noqa: E402
from sketch import (DRAW, GRAPHITE, ORANGE, Hatch, Item, Stroke,  # noqa: E402
                    fade_item, hatch_item, stroke_item, text_item)

from ballotreels.contest import load_contest  # noqa: E402
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
VOICE = vb.speech.load(CONTEST_DIR / 'narration.wav')
BOARD = lay_out(CONTEST, VOICE.seconds, FPS)
TRACK = VOICE.track_at(0, FPS)

PAPER_SCRAP = '#fbf7ec'
TAPE = (0.88, 0.82, 0.62, 0.62)

FADE = 12          # frames for a page, or a visual, to fade out (0.4 s)
DRAW_ON = 36       # frames a visual takes to draw on, at most (1.2 s)
BRIDGE = 6         # frames of gap the pencil crosses between two marks
PENCIL_FADE = 5    # frames for the pencil to fade in or out
WRITE_PX = 1500    # px of lettering a second


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
        header=Box(70, 204, 940, 76),
        heading=Box(70, 292, 940, 118),
        stage=Box(70, 430, 940, 870),
        scrap=Box(78, 1336, 924, 196),
        cards=Box(70, 430, 940, 1100),
        header_font=font(30, family=PRINT),
        heading_font=font(86, 700),
        chart_title_font=font(56, 700),
        label_font=font(46, 600),
        value_font=font(58, 700),
        note_font=font(34, family=PRINT),
        ballot_title_font=font(52, family=PRINT),
        option_font=font(84, 700),
        number_font=font(250, 700),
        number_label_font=font(64, 600),
        words_font=font(128, 700),
        timeline_font=font(46, family=PRINT),
        caption_font=font(58, family=PRINT),
        caption_lines=2,
        sources_font=font(48, family=PRINT),
    )


def layout_16x9():
    return dict(
        W=1920, H=1080, u=0.9,
        safe=Box(120, 124, 1680, 906),
        header=Box(120, 124, 1680, 40),
        heading=Box(120, 166, 1680, 96),
        stage=Box(150, 276, 1620, 540),
        scrap=Box(250, 842, 1420, 176),
        cards=Box(150, 276, 1620, 740),
        header_font=font(26, family=PRINT),
        heading_font=font(74, 700),
        chart_title_font=font(50, 700),
        label_font=font(42, 600),
        value_font=font(52, 700),
        note_font=font(31, family=PRINT),
        ballot_title_font=font(42, family=PRINT),
        option_font=font(64, 700),
        number_font=font(200, 700),
        number_label_font=font(56, 600),
        words_font=font(108, 700),
        timeline_font=font(40, family=PRINT),
        caption_font=font(54, family=PRINT),
        caption_lines=2,
        sources_font=font(42, family=PRINT),
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
    hb = L['heading']
    fnt = L['heading_font']
    words = sec_beat.section.heading
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
    # The two options, drawn alike: same oval, same lettering, same timing.
    for i, word in enumerate(('Yes', 'No')):
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
def source_note(chart, L, f0):
    """'Source: ...' along the stage's bottom, on the page from the visual's
    first frame to its last (rule 7.1): (item, box)."""
    stage = L['stage']
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
    """A bar that grows up from the baseline, its hatching revealed with it."""

    def __init__(self, x, base, w, h, seed, u):
        self.x, self.base, self.w, self.h = x, base, w, h
        top = base - h
        self.left = Stroke([(x, base), (x, top)], seed, passes=3, width=4.2 * u, overshoot=4)
        self.right = Stroke([(x + w, base), (x + w, top)], seed + 1, passes=3, width=4.2 * u, overshoot=4)
        self.top = Stroke([(x - 4, 0), (x + w + 6, 0)], seed + 2, passes=3, width=4.2 * u)
        self.fill = Hatch(box_pts(x, top, w, h), seed + 3, angle=52, spacing=13 * u, cross=True, alpha=0.42)

    def draw(self, cv, p):
        h = self.h * p
        if h <= 0:
            return
        top = self.base - h
        with cv.clip(self.x - 40, top - 6, self.w + 80, h + 30):
            self.fill.draw(cv, 1.0, GRAPHITE, 0.9)
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
    lf, vf, nf = L['label_font'], L['value_font'], L['note_font']
    n = len(v.values)
    vmax = max(max(v.values), 1e-9)
    slot = (plot.w - 120 * u) / n
    bw = min(slot * 0.55, 250 * u)
    lab_lines = [text.wrap(str(lb), lf, slot - 16 * u, balance=True) for lb in v.labels]
    lab_h = max(len(ls) for ls in lab_lines) * text.line_height(lf)
    base = plot.bottom - lab_h - 14 * u
    top = plot.y + text.line_height(vf) + 8 * u
    scale = (base - top) / vmax
    x0 = plot.x + 120 * u
    axis = Stroke([(x0 - 30 * u, base), (plot.right, base)], seed_of('axis'), passes=3, width=4.2 * u)
    items.append(stroke_item(f, f + 12, axis))
    zero = with_unit(0, v.unit)
    items.append(text_item(f + 8, f + 12, zero, nf, x0 - 40 * u, base - text.line_height(nf) * 0.55,
                           alpha=0.8, align='right', pencil=False))
    f += 14
    grow = 24
    # Every bar the same: same ink, hatching, weight, growth and timing (rule 7.4).
    for i, (val, ls) in enumerate(zip(v.values, lab_lines)):
        cx = x0 + slot * (i + 0.5)
        li, f, _ = write_lines(f, ls, lf, cx - slot / 2, base + 10 * u, align='center', width=slot)
        items += li
        bar = GrowBar(cx - bw / 2, base, bw, val * scale, seed_of('bar', i), u)
        items.append(Item(f + 2, f + 2 + grow, bar.draw, bar.head))
        f += 2 + grow
        vi, f, _ = write_lines(f + 2, [with_unit(val, v.unit)], vf, cx - slot / 2,
                               base - val * scale - text.line_height(vf) - 4 * u, align='center', width=slot)
        items += vi
        f += 6
    items = scaled(items, f0, draw_budget(f0, f1))
    return items, [Mark('chart', Box(plot.x, tbox.y, plot.w, plot.bottom - tbox.y)), Mark('chart source', sbox)]


# ---- the stage: a number, a phrase, a timeline ----
def fit_font(fnt, lines_of, width, max_lines, floor):
    """`fnt`, made smaller only if `lines_of(fnt)` (its wrapped lines) runs
    past `max_lines` lines or `width`: so two visuals of a kind share one
    size unless one cannot fit it (rule 7.4)."""
    while fnt.size > floor:
        lines = lines_of(fnt)
        if len(lines) <= max_lines and max(text.measure(ln, fnt) for ln in lines) <= width:
            break
        fnt = vb.Font(fnt.family, fnt.size * 0.92, weight=fnt.weight)
    return fnt, lines_of(fnt)


def number_visual(chart, lines, L, f0, f1):
    """One figure, large, with its short label under it and its source along
    the bottom. Every number is drawn alike: one ink, weight and size."""
    v = chart.visual
    stage = L['stage']
    u = L['u']
    src, sbox = source_note(chart, L, f0)
    nf, nlines = fit_font(L['number_font'], lambda f: [v.text], stage.w, 1, 60)
    lf, llines = fit_font(L['number_label_font'], lambda f: text.wrap(v.label, f, stage.w * 0.86, balance=True),
                          stage.w, 2, 30)
    nh, lh = text.line_height(nf), text.line_height(lf) * len(llines)
    gap = 18 * u
    y = stage.y + (sbox.y - stage.y - nh - gap - lh) / 2
    items, f, nbox = write_lines(f0, nlines, nf, stage.x, y, align='center', width=stage.w, speed=0.6)
    li, f, lbox = write_lines(f + 2, llines, lf, stage.x, y + nh + gap, align='center', width=stage.w)
    items = scaled([src] + items + li, f0, draw_budget(f0, f1))
    w = max(text.measure(ln, nf) for ln in nlines)
    box = Box(stage.cx - w / 2, nbox.y, w, lbox.bottom - nbox.y)
    return items, [Mark('chart', box), Mark('chart source', sbox)]


def words_visual(chart, lines, L, f0, f1):
    """A phrase of the line's own words, in large handwriting, centred on the
    stage. It cites nothing of its own: the line does."""
    v = chart.visual
    stage = L['stage']
    width = stage.w * 0.9
    fnt, wl = fit_font(L['words_font'], lambda f: text.wrap(v.text, f, width, balance=True), width, 3, 40)
    h = text.line_height(fnt) * len(wl)
    y = stage.cy - h / 2
    items, f, box = write_lines(f0, wl, fnt, stage.x, y, align='center', width=stage.w, speed=0.8)
    items = scaled(items, f0, draw_budget(f0, f1))
    w = max(text.measure(ln, fnt) for ln in wl)
    return items, [Mark('chart', Box(stage.cx - w / 2, box.y, w, box.h))]


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
            entry.append(stroke_item(f, f + 8, spine))
            f += 8
        dot = Stroke(sp.ellipse(spine_x, dot_y, 10 * u, 10 * u, n=20), seed_of('tdot'), passes=2,
                     width=4 * u, closed=True, overshoot=0)
        entry.append(stroke_item(f, f + 5, dot))
        di, f, _ = write_lines(f + 5, dl, df, tx, y)
        ii, f, _ = write_lines(f + 2, il, itf, tx, y + len(dl) * text.line_height(df))
        entry += di + ii
        nxt = starts[i + 1] if i + 1 < n else f1
        items += scaled(entry, s0, draw_budget(s0, nxt))
        prev_dot = dot_y
        y += h + gap
    box = Box(spine_x - 14 * u, top, stage.right - spine_x + 14 * u, y - gap - top)
    return items, [Mark('chart', box), Mark('chart source', sbox)]


SHARE_HATCH = [dict(angle=45, spacing=11, cross=False, alpha=0.5),
               dict(angle=-35, spacing=8, cross=True, alpha=0.36),
               dict(angle=0, spacing=13, cross=False, alpha=0.5),
               dict(angle=80, spacing=9, cross=False, alpha=0.45),
               dict(angle=20, spacing=15, cross=True, alpha=0.3)]


def share_chart(chart, L, f0, f1):
    """One column divided into parts, top to bottom in the labels' order,
    each labelled to its right with its value; it is the whole (100), so it
    starts at zero (rule 7.2)."""
    v = chart.visual
    u = L['u']
    items, f, plot, tbox, sbox = chart_frame(chart, L, f0)
    lf, vf = L['label_font'], L['value_font']
    col_w = 210 * u
    gap = 70 * u
    label_w = min(plot.w - col_w - gap, 560 * u)
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
        y = cy0
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
            items.append(hatch_item(f, f + 16, hatch))
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
    nf, vf = L['note_font'], L['label_font']
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
    step = max(1, math.ceil(n * 120 * u / (x1 - x0)))
    for i, lb in enumerate(v.labels):
        if i % step and i != n - 1:
            continue
        items.append(text_item(f, f + 3, str(lb), nf, xs(i), yb + 14 * u, alpha=0.85, align='center',
                               pencil=False))
        f += 1.5
    pts = [(xs(i), ys(val)) for i, val in enumerate(vals)]
    line = Stroke(pts, seed_of('series'), passes=3, width=4.4 * u, wobble=1.2, overshoot=0)
    d = max(30, 6 * n)
    items.append(stroke_item(f, f + d, line))
    f += d
    # the last point's value, beside it, so the line's end can be read
    x, y = pts[-1]
    dot = Stroke(sp.ellipse(x, y, 7 * u, 7 * u, n=16), seed_of('dot', n - 1), passes=2, width=3.6 * u,
                 closed=True, overshoot=0)
    items.append(stroke_item(f, f + 3, dot, pencil=False))
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
    lf = L['label_font']
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
    items.append(stroke_item(f, f + 26, sl))
    f += 26
    ex, ey = spend[-1]
    si, f, sbx = write_lines(f + 2, ['Spending'], lf, ex + 14 * u, ey - text.line_height(lf) * 0.55)
    items += si
    rl = Stroke(rev, seed_of('rev'), passes=3, width=4.4 * u, wobble=1.2, overshoot=0)
    items.append(stroke_item(f + 4, f + 44, rl))
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
        items.append(hatch_item(at(282 + 4 * (i - 4)), at(296), h, pencil=False))
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
                fill.draw(cv, 1.0, GRAPHITE, 0.9)
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
SHOWN = {'number': number_visual, 'words': words_visual, 'timeline': timeline_visual}


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

    def __init__(self, items, marks, f0, out=None):
        self.items, self.marks, self.f0, self.out = items, marks, f0, out

    def draw(self, cv, n):
        if n < self.f0 - 1 or (self.out is not None and n >= self.out + FADE):
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


def build(fmt):
    L = LAYOUTS[fmt]
    groups = []
    for sec in BOARD.sections:
        h_items, h_end, h_box = heading_items(sec, L, sec.start + (FADE if sec.number else 4))
        groups.append(Group(h_items, [Mark('heading', h_box, sec.start)], sec.start, sec.end))
        runs = runs_of(sec)
        for k, (kind, chart, lines) in enumerate(runs):
            start = lines[0].start
            first_f = max(h_end + 2, start + (FADE if start > sec.start else 0))
            end = lines[-1].end
            if kind == 'chart':
                items, marks = chart_run(chart, lines, L, first_f)
            else:
                items, marks = ballot_run(lines, L, first_f)
            for m in marks:
                m.f0 = first_f
            groups.append(Group(items, marks, start, end))
    # the closing sources card: never fades
    card_items, card_marks = sources_card(L, BOARD.narration_end + 8)
    groups.append(Group(card_items, card_marks, BOARD.narration_end))
    items = [it for g in groups for it in g.items]
    schedule = sorted((it for it in items if it._head), key=lambda it: it.f0)
    return dict(L=L, groups=groups, schedule=schedule, captions=caption_chunks(L))


def sources_card(L, f0):
    hb = L['heading']
    box = L['cards']
    u = L['u']
    fnt = L['heading_font']
    items, f, hbox = write_lines(f0, ['Sources'], fnt, hb.x, hb.y + 6, align='center', width=hb.w)
    w = text.measure('Sources', fnt)
    under = Stroke([(hb.cx - w / 2 - 6, hbox.bottom + 2), (hb.cx + w / 2 + 8, hbox.bottom + 4)],
                   seed_of('underline'), passes=2, width=5 * u)
    items.append(stroke_item(f + 1, f + 9, under, ORANGE))
    f += 10
    sf = L['sources_font']
    num_w = 50 * u
    while True:
        blocks = [text.wrap(s.publisher, sf, box.w - num_w, balance=True) for s in BOARD.cited]
        gap = text.line_height(sf) * 0.45
        total = sum(len(b) * text.line_height(sf) for b in blocks) + gap * (len(blocks) - 1)
        if total <= box.h - 20 * u or sf.size < 22:
            break
        sf = font(sf.size * 0.94, family=PRINT)
    y = box.y + max(0, (box.h - total) / 2 - 30 * u)
    top = y
    for i, lines in enumerate(blocks):
        ni, _, _ = write_lines(f, [f'{i + 1}.'], sf, box.x, y, speed=2)
        items += ni
        li, f, _ = write_lines(f + 2, lines, sf, box.x + num_w, y, speed=2.2)
        items += li
        y += len(lines) * text.line_height(sf) + gap
        f += 3
    return items, [Mark('heading', hbox), Mark('sources', Box(box.x, top, box.w, y - gap - top))]


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
    phrases = VOICE.phrases
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
        nxt = phrases[pi + 1].start if pi + 1 < len(phrases) else VOICE.seconds + 0.5
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


def scrap_edge(L):
    key = L['W']
    if key not in _SCRAPS:
        s = L['scrap']
        _SCRAPS[key] = paths.torn([(s.x, s.y), (s.right, s.y + 4), (s.right - 3, s.bottom), (s.x + 2, s.bottom - 3)],
                                  seed=91, amount=5, step=3)
    return _SCRAPS[key]


def draw_captions(cv, n, P):
    L = P['L']
    t = n / FPS
    s = L['scrap']
    ctx = cv.ctx
    edge = scrap_edge(L)
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
    cv.mark('caption', s.x, s.y, s.w, s.h)


# ---- the running header: the measure's title, on every page ----
def draw_header(cv, L):
    hb = L['header']
    fnt = L['header_font']
    lines = text.wrap(CONTEST.title, fnt, hb.w, balance=True)
    drawn = sp.pencil_text(cv, lines, fnt, hb.x, hb.y, GRAPHITE, 0.62, align='center', width=hb.w)
    cv.mark('header', *drawn)


# ---- the pencil: only while something is being drawn ----
def pencil_at(n, P):
    """(x, y, ink, alpha) of the pencil tip at frame n, or None. It follows
    whatever is being drawn; across a short gap between two marks it moves
    straight from one to the next, and otherwise it fades out where it
    stopped (and in where it starts). It never travels or idles."""
    prev = nxt = None
    for it in P['schedule']:
        if it.f0 <= n <= it.f1:
            x, y = it.head(n)
            return x, y, it.ink, 1.0
        if it.f1 < n:
            if prev is None or it.f1 > prev.f1:
                prev = it
        elif it.f0 > n:
            nxt = it
            break
    fa = prev.f1 if prev else -1e9
    fb = nxt.f0 if nxt else 1e9
    if fb - fa <= BRIDGE:
        a, b = prev.head(fa), nxt.head(fb)
        q = DRAW(vb.clamp01((n - fa) / (fb - fa)))
        return a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q, nxt.ink, 1.0
    if n - fa < PENCIL_FADE:
        x, y = prev.head(fa)
        return x, y, prev.ink, 1 - (n - fa) / PENCIL_FADE
    if fb - n < PENCIL_FADE:
        x, y = nxt.head(fb)
        return x, y, nxt.ink, 1 - (fb - n) / PENCIL_FADE
    return None


def draw_pencil(cv, n, P):
    at = pencil_at(n, P)
    if not at:
        return
    x, y, ink, alpha = at
    colour = None if ink == GRAPHITE else ink
    if alpha >= 1:
        sp.draw_pencil(cv, x, y, colour)
        return
    with cv.layer(opacity=alpha):
        sp.draw_pencil(cv, x, y, colour)


# ---- the frame ----
PLANS = {fmt: build(fmt) for fmt in LAYOUTS}


def draw(n, cv):
    P = PLANS[cv.format.name]
    ctx = cv.ctx
    ctx.set_source_surface(sp.backdrop(cv.width, cv.height), 0, 0)
    ctx.paint()
    draw_header(cv, P['L'])
    for g in P['groups']:
        g.draw(cv, n)
    draw_pencil(cv, n, P)
    if n < BOARD.narration_end:
        draw_captions(cv, n, P)


SEGMENTS = [vb.Segment(s.label, s.start, s.end,
                       data={'copy': [s.section.heading] + [b.line.text for b in s.lines]})
            for s in BOARD.sections]
SEGMENTS.append(vb.Segment('sources', BOARD.narration_end, BOARD.end,
                           data={'copy': ['Sources'] + [s.publisher for s in BOARD.cited]}))
TIMELINE = vb.Timeline(GRID, SEGMENTS, end=BOARD.end)

FILM = vb.Film(
    draw=draw,
    timeline=TIMELINE,
    formats=('9x16', '16x9'),
    background='#f2ebd8',
    sounds=(VOICE.sound(at=0, fps=FPS),),
)

if __name__ == '__main__':
    vb.main(__file__)
