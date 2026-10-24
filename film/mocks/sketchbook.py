"""Style mock: a pencil sketchbook. Prop 2's Rainy Day Fund in 20 seconds.

    PYTHONPATH=$VB python film/mocks/sketchbook.py sheet --format 9x16
    PYTHONPATH=$VB python film/mocks/sketchbook.py render --format 9x16

Graphite on a cream grid page, one orange coloured pencil for emphasis.
Every line is built from a few light, overlapping passes and is drawn on
by a pencil as the narrator speaks; the chart is rubbed out with an eraser
when the film moves on, leaving a ghost and a smudge. The storyboard and
narration are shared with the other style mocks (film/mocks/narration.*).

Time is in frames (one frame a beat, as in film/measure.py): cuts follow
the narration, not a music grid. All drawing is in absolute 1080x1920 page
coordinates; this mock is 9:16 only.
"""
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import cairo  # noqa: E402

import videobuilder as vb  # noqa: E402
from videobuilder import Box, text  # noqa: E402

import sketchbook_pencil as sp  # noqa: E402
from sketchbook_pencil import GRAPHITE, ORANGE, Hatch, Stroke  # noqa: E402

for _f in sorted((HERE.parent / 'assets' / 'fonts').glob('*.[ot]tf')):
    text.register(_f)
HAND = 'Caveat'          # labels: a quick, slanted hand
PRINT = 'Patrick Hand'   # captions and small notes: a neater, rounder hand

FPS = 30
GRID = vb.Grid(fps=FPS, bpm=FPS * 60)  # one frame a beat


def fr(seconds):
    return vb.round_half_up(seconds * FPS)


VOICE = vb.speech.load(HERE / 'narration.wav')
TRACK = VOICE.track_at(0, FPS)


# ---- storyboard (shared by every style mock; frames) ----
def seg(name, at, until, copy='', overlap=0, **data):
    return vb.Segment(name, at, until, dict(copy=copy, **data), overlap=overlap)


SOURCE = "Source: Legislative Analyst's Office"
TIMELINE = vb.Timeline(GRID, [
    seg('rise', 0, 123, ['tax revenue', 'years', 'illustrative, not real data']),
    seg('plunge', 123, 246, 'tens of billions', copy_at=63),
    seg('fund', 246, 357, 'Rainy Day Fund', copy_at=50, overlap=24),
    seg('today', 357, 498, 'Today: 10%', copy_at=89),
    # The source line is written in the narration gap before this phrase and
    # stays to the end; it is a footnote, so it isn't held to a read time.
    seg('prop2', 498, 615, 'Prop 2: 20%', copy_at=56, source=SOURCE),
], end=615)
D = {s.name: s.data for s in TIMELINE.segments}

SAFE = Box(70, 220, 940, 1320)   # 9:16: 220 top, 380 bottom, 70 sides


def font(size, weight=400, family=HAND, **kw):
    return vb.Font(family, size, weight=weight, **kw)


DRAW = vb.bezier(0.42, 0, 0.3, 1)   # a hand: starts deliberately, eases into the end


# ---- things drawn on: each knows when, and where the pencil tip is ----
class Item:
    """One mark on the page, drawn on from frame `f0` to `f1`. `head(p)` is
    where the pencil tip is at progress p (None: no pencil, e.g. shading laid
    in behind the main line); `ink` the pencil's colour."""

    def __init__(self, f0, f1, draw, head=None, ink=GRAPHITE, ease=DRAW):
        self.f0, self.f1, self._draw, self._head, self.ink, self.ease = f0, f1, draw, head, ink, ease

    def p(self, n):
        return self.ease(vb.clamp01((n - self.f0) / max(1, self.f1 - self.f0)))

    def draw(self, cv, n, full=False):
        p = 1.0 if full else self.p(n)
        if p > 0:
            self._draw(cv, p)

    def head(self, n):
        return self._head(self.p(n)) if self._head else None


def stroke_item(f0, f1, stroke, ink=GRAPHITE, alpha=1.0, pencil=True):
    return Item(f0, f1, lambda cv, p: stroke.draw(cv, p, ink, alpha),
                stroke.head if pencil else None, ink)


def hatch_item(f0, f1, hatch, ink=GRAPHITE, alpha=1.0, pencil=True):
    return Item(f0, f1, lambda cv, p: hatch.draw(cv, p, ink, alpha),
                hatch.head if pencil else None, ink, ease=vb.linear)


def text_item(f0, f1, words, fnt, x, y, ink=GRAPHITE, alpha=1.0, align='left', mark=None, pencil=True):
    """Lettering written on left to right (one line). `x` is the left edge,
    or the centre / right edge for align 'center' / 'right'."""
    w = text.measure(words, fnt)
    h = text.line_height(fnt)
    left = {'left': x, 'center': x - w / 2, 'right': x - w}[align]

    def draw(cv, p):
        with cv.clip(left - 30, y - 40, 30 + (w + 60) * p, h + 80):
            sp.pencil_text(cv, words, fnt, left, y, ink, alpha)
        if mark and p >= 1 and not getattr(cv, '_sb_nomark', False):
            cv.mark(mark, left, y, w, h)

    def head(p):
        return (left + w * p, y + h * (0.62 + 0.12 * math.sin(p * w / 16)))

    return Item(f0, f1, draw, head if pencil else None, ink, ease=vb.linear)


# ---- scene 1: the chart (rise, plunge) ----
X0, X1, YB, YT = 150, 990, 1080, 500   # plot: x axis at YB, value 1 at YT
VALUES = [0.40, 0.53, 0.45, 0.63, 0.55, 0.73, 0.64, 0.92, 0.56, 0.32, 0.43, 0.52]
PEAK, TROUGH = 7, 9


def vx(i):
    return 175 + i * 69


def vy(v):
    return YB - v * (YB - YT)


PER = 14
CURVE = sp.catmull([(vx(i), vy(v)) for i, v in enumerate(VALUES)], per=PER)
RISE_PTS = CURVE[:PEAK * PER + 1]
PLUNGE_PTS = CURVE[PEAK * PER:TROUGH * PER + 1]
TAIL_PTS = CURVE[TROUGH * PER:]
PEAK_XY, TROUGH_XY = CURVE[PEAK * PER], CURVE[TROUGH * PER]
ARROW_X = 968

T_LABEL = font(64, 700)
T_NOTE = font(42, family=PRINT)
T_CALLOUT = font(84, 700)

CHART = []
CHART_GHOST = []   # what's left after the eraser


def _chart():
    c = CHART
    # construction: a light guide box first, as a draughtsman blocks it in
    for i, (a, b) in enumerate([((X0 - 30, YT - 10), (X1 + 25, YT - 10)), ((X1, YT - 40), (X1, YB + 30))]):
        c.append(stroke_item(2 + 3 * i, 10 + 3 * i, Stroke([a, b], 40 + i, passes=1, width=1.6, alpha=0.22,
                                                           wobble=1, overshoot=0), pencil=False))
    c.append(stroke_item(3, 17, Stroke([(X0, YT - 40), (X0, YB + 6)], 1, passes=3)))
    c.append(stroke_item(17, 33, Stroke([(X0 - 8, YB), (X1 + 10, YB)], 2, passes=3)))
    # tick marks along the years
    for i in range(len(VALUES)):
        c.append(stroke_item(30 + i, 33 + i, Stroke([(vx(i), YB - 2), (vx(i), YB + 14)], 60 + i, passes=1,
                                                    width=2.4, overshoot=2), pencil=False))
    c.append(text_item(30, 46, D['rise']['copy'][0], T_LABEL, X0 + 22, YT - 118, mark='axis label'))
    c.append(text_item(46, 54, D['rise']['copy'][1] + ' →', font(54, 600), X0 + 4, YB + 22, mark='years'))
    c.append(text_item(56, 76, D['rise']['copy'][2], T_NOTE, X1 + 10, YB + 30, alpha=0.75,
                       align='right', mark='note'))
    # the revenue line, swinging up and down, then shading under it
    c.append(stroke_item(78, 116, Stroke(RISE_PTS, 3, passes=3, width=4.2, wobble=1.4)))
    under = RISE_PTS + PLUNGE_PTS[1:] + TAIL_PTS[1:] + [(TAIL_PTS[-1][0], YB), (RISE_PTS[0][0], YB)]
    shade = Hatch(under, 4, angle=62, spacing=15, alpha=0.36, width=2.0)
    c.append(Item(80, 230, lambda cv, p: _shade_under(cv, shade), None))
    # the plunge, in orange
    c.append(stroke_item(136, 154, Stroke(PLUNGE_PTS, 5, passes=3, width=5.0, wobble=1.2), ORANGE))
    c.append(stroke_item(154, 164, Stroke(TAIL_PTS, 6, passes=2, width=4.2)))
    # guide lines at the peak and the trough, and the drop between them
    for k, (xy, f) in enumerate(((PEAK_XY, 158), (TROUGH_XY, 162))):
        for j, d in enumerate(sp.dashes([(xy[0] + 14, xy[1]), (ARROW_X + 24, xy[1])], 16, 11)):
            c.append(stroke_item(f + j * 0.6, f + j * 0.6 + 2, Stroke(d, 70 + 10 * k + j, passes=1, width=2.4,
                                                                    overshoot=1, wobble=0.6), pencil=False))
    lost = PLUNGE_PTS + [(TROUGH_XY[0], PEAK_XY[1])]
    c.append(hatch_item(164, 186, Hatch(lost, 8, angle=-35, spacing=12, alpha=0.6, width=2.4), ORANGE,
                        pencil=False))
    top, bot = PEAK_XY[1] + 6, TROUGH_XY[1] - 6
    c.append(stroke_item(164, 174, Stroke([(ARROW_X, top), (ARROW_X, bot)], 9, passes=2, width=4), ORANGE,
                         pencil=False))
    for k, (y, s) in enumerate(((top, 1), (bot, -1))):
        c.append(stroke_item(174 + 2 * k, 177 + 2 * k,
                             Stroke([(ARROW_X - 17, y + 22 * s), (ARROW_X, y), (ARROW_X + 17, y + 22 * s)],
                                    11 + k, passes=2, width=4, overshoot=2), ORANGE, pencil=False))
    # the callout sits just above the peak's guide, ending over the arrow
    words = D['plunge']['copy']
    w = text.measure(words, T_CALLOUT)
    c.append(text_item(166, 186, words, T_CALLOUT, ARROW_X + 20 - w,
                       PEAK_XY[1] - 16 - text.line_height(T_CALLOUT), ORANGE, mark='callout'))


def _shade_under(cv, shade):
    # The shading trails the pencil along the line, so clip it to the line's head.
    n = cv._sb_n
    hx = X0
    for it in (CHART[_RISE], CHART[_PLUNGE], CHART[_TAIL]):
        h = it.head(n)
        if it.p(n) > 0:
            hx = h[0]
    a = vb.clamp01((n - 84) / 12)
    with cv.clip(0, 0, hx - 12, cv.height):
        shade.draw(cv, 1.0, GRAPHITE, a)


_chart()
_RISE = next(i for i, it in enumerate(CHART) if it.f0 == 78)
_PLUNGE = next(i for i, it in enumerate(CHART) if it.f0 == 136)
_TAIL = next(i for i, it in enumerate(CHART) if it.f0 == 154)

ERASE0, ERASE1 = 240, 264   # the eraser's pass, under the fund scene's first beat
ZIGZAG = []
for _i in range(8):
    _y = 330 + _i * 118
    ZIGZAG += [(90, _y), (1010, _y + 40)] if _i % 2 == 0 else [(1010, _y), (90, _y + 40)]
ZIGZAG = sp.catmull(ZIGZAG, per=6)


def chart_scene(cv, n):
    if n < ERASE0:
        for it in CHART:
            it.draw(cv, n)
        cv.mark('chart', X0 - 10, YT - 30, X1 - X0 + 30, YB - YT + 40)
        return
    # the eraser rubs the chart out; a ghost and a smudge stay on the page
    e = vb.clamp01((n - ERASE0) / (ERASE1 - ERASE0))
    ctx = cv.ctx
    ctx.push_group()
    cv._sb_nomark = True
    for it in CHART:
        it.draw(cv, n, full=True)
    cv._sb_nomark = False
    ctx.set_operator(cairo.OPERATOR_DEST_OUT)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    rubbed = vb.paths.reveal(ZIGZAG, e)
    if len(rubbed) >= 2:
        ctx.new_path()
        sp._path(ctx, rubbed)
        ctx.set_line_width(190)
        ctx.set_source_rgba(0, 0, 0, 0.93)
        ctx.stroke()
    ctx.set_operator(cairo.OPERATOR_OVER)
    ctx.pop_group_to_source()
    ghost = vb.interpolate(n, [ERASE1, 357], [1, 0.0])
    ctx.paint_with_alpha(ghost)
    smudge = vb.clamp01(e * 1.2) * ghost
    if smudge > 0:
        ctx.set_source_surface(_smudge(), 0, 0)
        ctx.paint_with_alpha(smudge)
    if e < 1:
        x, y = rubbed[-1] if rubbed else ZIGZAG[0]
        sp.draw_eraser(cv, x, y + 10 * math.sin(n * 1.7), -0.3 + 0.12 * math.sin(n * 0.9))


_SMUDGE = []


def _smudge():
    if not _SMUDGE:
        from PIL import Image, ImageDraw, ImageFilter
        img = Image.new('L', (1080, 1920), 0)
        d = ImageDraw.Draw(img)
        rnd = random.Random(21)
        pts = vb.paths.resample(ZIGZAG, 60)
        for x, y in pts:
            r = rnd.uniform(30, 70)
            d.ellipse([x - r * 1.6, y - r * 0.5, x + r * 1.6, y + r * 0.5], fill=rnd.randint(20, 46))
        img = img.filter(ImageFilter.GaussianBlur(26))
        rgba = Image.merge('RGBA', [Image.new('L', img.size, 70)] * 3 + [img])
        _SMUDGE.insert(0, _to_surface(rgba))
    return _SMUDGE[0]


def _to_surface(pil):
    import numpy as np
    a = np.asarray(pil).astype('float32') / 255
    al = a[..., 3:4]
    pre = (a[..., :3] * al * 255).astype('uint8')
    bgra = np.concatenate([pre[..., 2:3], pre[..., 1:2], pre[..., 0:1], (al * 255).astype('uint8')], axis=2)
    data = bytearray(bgra.tobytes())
    surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, pil.width, pil.height, pil.width * 4)
    _SMUDGE.append(data)  # cairo borrows the buffer; keep it alive
    return surf


# ---- scene 2: the Rainy Day Fund ----
C = (560, 540)          # canopy centre, page coordinates
ROT = -0.24             # canopy tilted to shelter the jar
RX, RY = 370, 290
RIBS = 6


def _tilt(pts):
    cr, sr = math.cos(ROT), math.sin(ROT)
    return [(C[0] + x * cr - y * sr, C[1] + x * sr + y * cr) for x, y in pts]


def _rib(xk):
    return [(xk * math.sin(t * math.pi / 2 / 20), -RY * math.cos(t * math.pi / 2 / 20)) for t in range(21)]


def _scallop(xa, xb):
    return [(xa + (xb - xa) * t / 12, -30 * math.sin(math.pi * t / 12)) for t in range(13)]


EDGES = [-RX + k * 2 * RX / RIBS for k in range(RIBS + 1)]
CANOPY_TOP = _tilt(sp.ellipse(0, 0, RX, RY, math.pi, 2 * math.pi, n=60))
SCALLOPS = [_tilt(_scallop(a, b)) for a, b in zip(EDGES, EDGES[1:])]
RIB_LINES = [_tilt(_rib(x)) for x in EDGES[1:-1]]
PANELS = []
for _k, (_a, _b) in enumerate(zip(EDGES, EDGES[1:])):
    PANELS.append(_tilt(_rib(_a) + _scallop(_a, _b)[1:] + _rib(_b)[::-1][1:]))
SHAFT = _tilt([(0, -RY - 42), (0, -RY)]), _tilt([(0, -8), (0, 560)])
HOOK = _tilt([(0, 560)] + [(38 - 38 * math.cos(t * math.pi / 14), 560 + 38 * math.sin(t * math.pi / 14))
                           for t in range(1, 15)] + [(76, 548)])

JX = 420
JAR_PTS = sp.catmull([(300, 790), (300, 818), (276, 852), (274, 960), (274, 1108), (300, 1146),
                      (420, 1150), (540, 1146), (566, 1108), (566, 960), (564, 852), (540, 818), (540, 790)],
                     per=8)
RIM = sp.ellipse(JX, 790, 122, 17)
GROUND = [(190, 1160), (470, 1156), (840, 1161)]

T_FUND = font(96, 700)
FUND = []
COINS = []


def _fund():
    f = FUND
    # canopy: the top in one sweep, then the scalloped hem, ribs, shaft and hook
    f.append(stroke_item(258, 272, Stroke(CANOPY_TOP, 20, passes=3, width=4.4)))
    hem = [p for s in SCALLOPS for p in s[:-1]] + [SCALLOPS[-1][-1]]
    f.append(stroke_item(272, 280, Stroke(hem, 21, passes=2, width=3.8), pencil=False))
    for k, rib in enumerate(RIB_LINES):
        f.append(stroke_item(276 + 1.6 * k, 279 + 1.6 * k, Stroke(rib, 22 + k, passes=2, width=3), pencil=False))
    f.append(stroke_item(278, 281, Stroke(SHAFT[0], 30, passes=2, width=5), pencil=False))
    f.append(stroke_item(280, 288, Stroke(SHAFT[1] + HOOK[1:], 31, passes=3, width=5.4), pencil=False))
    for k in (4, 5):
        f.append(hatch_item(282 + 4 * (k - 4), 296, Hatch(PANELS[k], 40 + k, angle=-58, spacing=13,
                                                        cross=k == 5, alpha=0.38), pencil=False))
    # the jar, its rim and a glint on the glass
    f.append(stroke_item(298, 312, Stroke(JAR_PTS, 32, passes=3, width=4)))
    f.append(stroke_item(312, 318, Stroke(RIM, 33, passes=2, width=3.4, closed=True)))
    for k, (x0, y0, y1) in enumerate(((296, 880, 990), (304, 1010, 1040))):
        f.append(stroke_item(318, 320, Stroke([(x0, y0), (x0 - 2, y1)], 34 + k, passes=1, width=3, alpha=0.5),
                             pencil=False))
    f.append(hatch_item(318, 330, Hatch([(530, 860), (556, 880), (556, 1100), (530, 1130)], 36, angle=80,
                                         spacing=10, alpha=0.32), pencil=False))
    f.append(stroke_item(316, 324, Stroke(GROUND, 37, passes=2, width=3), pencil=False))
    f.append(hatch_item(320, 332, Hatch(sp.ellipse(JX + 30, 1160, 200, 14), 38, angle=20, spacing=8, alpha=0.4),
                        pencil=False))
    # the label, underlined in orange
    words = D['fund']['copy']
    f.append(text_item(278, 296, words, T_FUND, JX + 50, 1166, align='center', mark='fund label'))
    w = text.measure(words, T_FUND)
    f.append(stroke_item(336, 344, Stroke(sp.catmull([(JX + 50 - w / 2, 1286), (JX + 50, 1281),
                                                       (JX + 50 + w / 2 + 8, 1288)], per=10), 39, passes=2,
                                          width=5), ORANGE))
    # coins dropping into the jar as the state saves
    rnd = random.Random(50)
    rows = [(1104, [318, 388, 456, 523]), (1060, [352, 422, 490]), (1018, [386, 456])]
    k = 0
    for y, xs in rows:
        for x in xs:
            ry = rnd.uniform(0.4, 0.95)
            rot = rnd.uniform(-0.5, 0.5)
            outer = Stroke(sp.ellipse(0, 0, 33, 33 * ry, rot=rot, n=36), 100 + k, passes=2, width=3, closed=True)
            inner = Stroke(sp.ellipse(0, 0, 22, 22 * ry, rot=rot, n=30), 120 + k, passes=1, width=2, alpha=0.5,
                           closed=True)
            fill = Hatch(sp.ellipse(0, 0, 30, 30 * ry, rot=rot, n=24), 140 + k, angle=40, spacing=7,
                         alpha=0.55, width=2)
            COINS.append(dict(x=x + rnd.uniform(-4, 4), y=y + rnd.uniform(-3, 3), f=306 + 2.6 * k,
                              outer=outer, inner=inner, fill=fill, spin=rnd.uniform(-3, 3)))
            k += 1


_fund()


def draw_coin(cv, c, n, full=False):
    t = 1.0 if full else vb.clamp01((n - c['f']) / 11)
    if t <= 0:
        return
    drop = 660 - c['y'] + 40 * math.sin(c['x'])
    # falls with gravity, settles with a small bounce
    y = c['y'] - drop * (1 - t * t) if t < 1 else c['y']
    b = vb.clamp01((n - c['f'] - 11) / 6) if not full else 1
    if t >= 1 and b < 1:
        y -= 9 * math.sin(b * math.pi)
    ctx = cv.ctx
    ctx.save()
    ctx.translate(c['x'], y)
    ctx.rotate((1 - t) * c['spin'])
    c['fill'].draw(cv, 1.0, ORANGE, 0.85)
    c['outer'].draw(cv, 1.0, GRAPHITE)
    c['inner'].draw(cv, 1.0, GRAPHITE)
    ctx.restore()


RAIN = [(random.Random(70 + i).uniform(80, 1010), random.Random(170 + i).uniform(0, 1)) for i in range(54)]
RAIN_TOP, RAIN_GROUND, RAIN_SPEED = 232, 1150, 21


def _canopy_y(x):
    pts = CANOPY_TOP
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def draw_rain(cv, n, alpha):
    if alpha <= 0:
        return
    ctx = cv.ctx
    ctx.save()
    ctx.new_path()
    span = RAIN_GROUND - RAIN_TOP
    for x, ph in RAIN:
        y = RAIN_TOP + (ph * span + n * RAIN_SPEED) % span
        stop = _canopy_y(x)
        bottom = stop if stop is not None else RAIN_GROUND
        if y + 26 > bottom:
            continue
        ctx.move_to(x, y)
        ctx.line_to(x - 5, y + 26)
    ctx.set_line_width(2.6)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source(sp.ink(GRAPHITE, 0.5 * alpha))
    ctx.stroke()
    ctx.restore()


def fund_drawing(cv, n, full=False, marks=True):
    """The umbrella, jar, coins and label; `full` draws it finished."""
    draw_rain(cv, n, 1.0 if full else vb.clamp01((n - 280) / 15))
    for it in FUND:
        it.draw(cv, n, full)
    for c in COINS:
        draw_coin(cv, c, n, full)
    if marks:
        cv.mark('fund', 190, 232, 760, 932)


def fund_scene(cv, n):
    fund_drawing(cv, n)


# ---- scene 3: the bars ----
ICON_S = 0.42
ICON_AT = (82, 236)     # where the fund's top-left (190, 232) goes once it's a margin sketch
BASE_Y = 1150
BAR_W = 236
BARS = [(250, 0.10, D['today']['copy']), (640, 0.20, D['prop2']['copy'])]
PX_PER_PCT = 2300       # 10% is 230 px
T_BAR = font(86, 700)

BAR_ITEMS = []


def _bars():
    b = BAR_ITEMS
    b.append(stroke_item(378, 392, Stroke([(120, BASE_Y), (1000, BASE_Y)], 200, passes=3, width=4.2)))
    b.append(text_item(388, 394, '0%', font(44, family=PRINT), 112, BASE_Y - 20, alpha=0.8, align='right',
                       pencil=False, mark='zero'))
    # a light guide at the 10% line, carried across to where the second bar will go
    y10 = BASE_Y - 0.10 * PX_PER_PCT
    b.append(stroke_item(466, 482, Stroke([(BARS[0][0] + BAR_W + 8, y10), (BARS[1][0] + BAR_W + 30, y10)], 201,
                                          passes=1, width=1.8, alpha=0.3, overshoot=0), pencil=False))
    b.append(text_item(484, 498, SOURCE, font(40, family=PRINT), 540, BASE_Y + 16, alpha=0.75, align='center',
                       mark='source'))


_bars()


class Bar:
    def __init__(self, x, pct, label, seed, ink, grow):
        self.x, self.h, self.label, self.ink, self.grow = x, pct * PX_PER_PCT, label, ink, grow
        top = BASE_Y - self.h
        self.left = Stroke([(x, BASE_Y), (x, top)], seed, passes=3, width=4.2, overshoot=4)
        self.right = Stroke([(x + BAR_W, BASE_Y), (x + BAR_W, top)], seed + 1, passes=3, width=4.2, overshoot=4)
        self.top = Stroke([(x - 4, 0), (x + BAR_W + 6, 0)], seed + 2, passes=3, width=4.2)
        self.fill = Hatch([(x, BASE_Y), (x, top), (x + BAR_W, top), (x + BAR_W, BASE_Y)], seed + 3,
                          angle=52, spacing=13, cross=ink == GRAPHITE,
                          alpha=0.42 if ink == GRAPHITE else 0.7)

    def height(self, n):
        return self.h * self.grow(n)

    def draw(self, cv, n):
        h = self.height(n)
        if h <= 0:
            return
        top = BASE_Y - h
        ctx = cv.ctx
        with cv.clip(self.x - 40, top - 6, BAR_W + 80, h + 30):
            self.fill.draw(cv, 1.0, self.ink, 0.9)
            self.left.draw(cv, 1.0)
            self.right.draw(cv, 1.0)
        ctx.save()
        ctx.translate(0, top)
        self.top.draw(cv, 1.0)
        ctx.restore()
        cv.mark('bar ' + self.label, self.x - 6, top - 6, BAR_W + 14, h + 6)

    def head(self, n):
        return (self.x + BAR_W * 0.55, BASE_Y - self.height(n))


def _grow_today(n):
    return DRAW(vb.clamp01((n - 396) / 26))


def _grow_prop2(n):
    # up to the old 10% line, a beat's pause, then on to twice the height
    a = DRAW(vb.clamp01((n - 504) / 14)) * 0.5
    s = vb.spring_at(n - 520, FPS, **vb.damped(0.62, hz=1.3)) if n >= 520 else 0.0
    return a + 0.5 * s


BAR_OBJS = [Bar(BARS[0][0], BARS[0][1], BARS[0][2], 210, GRAPHITE, _grow_today),
            Bar(BARS[1][0], BARS[1][1], BARS[1][2], 220, ORANGE, _grow_prop2)]
BAR_ITEMS.append(Item(396, 422, lambda cv, p: None, lambda p: BAR_OBJS[0].head(396 + p * 26), ease=vb.linear))
BAR_ITEMS.append(Item(504, 530, lambda cv, p: None, lambda p: BAR_OBJS[1].head(504 + p * 26), ORANGE,
                      ease=vb.linear))
for _b, (_f0, _f1) in zip(BAR_OBJS, ((424, 446), (534, 554))):
    _top = BASE_Y - _b.h
    BAR_ITEMS.append(text_item(_f0, _f1, _b.label, T_BAR, _b.x + BAR_W / 2, _top - 116, align='center',
                               mark='label ' + _b.label))


def icon_transform(n):
    """Fund drawing -> margin sketch, over the first frames of the bars."""
    q = vb.ease_in_out_quart(vb.clamp01((n - 357) / 20))
    s = 1 + (ICON_S - 1) * q
    dx = (ICON_AT[0] - 190 * ICON_S) * q + 0 * (1 - q)
    dy = (ICON_AT[1] - 232 * ICON_S) * q
    return s, dx, dy


def bars_scene(cv, n):
    s, dx, dy = icon_transform(n)
    with cv.layer(dx=dx, dy=dy, scale=s):
        cv._sb_nomark = True
        fund_drawing(cv, n, full=True, marks=False)
        cv._sb_nomark = False
    cv.mark('fund sketch', 190 * s + dx, 232 * s + dy, 760 * s, 1100 * s)
    for it in BAR_ITEMS:
        it.draw(cv, n)
    for b in BAR_OBJS:
        b.draw(cv, n)


# ---- the pencil: follows whatever is being drawn, travels or lifts between ----
SCHEDULE = sorted((it for it in CHART + FUND + BAR_ITEMS if it._head), key=lambda it: it.f0)
REST = (1180, 1500)   # off the page, bottom right


def pencil_at(n):
    """(x, y, ink, lift) of the pencil tip at frame n, or None when off the page."""
    prev = nxt = None
    for it in SCHEDULE:
        if it.f0 <= n <= it.f1:
            x, y = it.head(n)
            return x, y, it.ink, 0.0
        if it.f1 < n:
            prev = it
        elif nxt is None and it.f0 > n:
            nxt = it
    a = prev.head(prev.f1) if prev else REST
    b = nxt.head(nxt.f0) if nxt else REST
    fa = prev.f1 if prev else -1e9
    fb = nxt.f0 if nxt else 1e9
    if fb - fa <= 30:   # hop to the next mark
        q = DRAW(vb.clamp01((n - fa) / (fb - fa)))
        ink = nxt.ink if q > 0.5 else prev.ink
        return a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q, ink, math.sin(q * math.pi)
    if n - fa <= 12:     # lift away
        q = DRAW((n - fa) / 12)
        return a[0] + (REST[0] - a[0]) * q, a[1] + (REST[1] - a[1]) * q, prev.ink, q
    if fb - n <= 12:     # come back in
        q = DRAW((fb - n) / 12)
        return b[0] + (REST[0] - b[0]) * q, b[1] + (REST[1] - b[1]) * q, nxt.ink, q
    return None


def draw_tool(cv, n):
    if ERASE0 <= n < ERASE1:
        return
    at = pencil_at(n)
    if at is None:
        return
    x, y, ink, lift = at
    sp.draw_pencil(cv, x, y, None if ink == GRAPHITE else ink, lift)


# ---- captions: the whole phrase on a taped scrap, ink darkening as it's spoken ----
SCRAP = Box(78, 1336, 924, 196)
T_CAP = font(60, family=PRINT)
_r = random.Random(90)
SCRAP_EDGE = vb.paths.torn([(SCRAP.x, SCRAP.y), (SCRAP.right, SCRAP.y + 4), (SCRAP.right - 3, SCRAP.bottom),
                            (SCRAP.x + 2, SCRAP.bottom - 3)], seed=91, amount=5, step=3)


def _phrases():
    words = list(TRACK)
    out = []
    for i, ph in enumerate(VOICE.phrases):
        ws = [w for w in words if ph.start - 0.05 <= w.start < ph.end + 0.05]
        nxt = VOICE.phrases[i + 1].start if i + 1 < len(VOICE.phrases) else 99
        size = T_CAP.size
        while True:
            fnt = font(size, family=PRINT)
            lines = text.wrap(ph.text, fnt, SCRAP.w - 90, balance=True)
            if len(lines) <= 2:
                break
            size *= 0.95
        out.append(dict(start=ph.start - 0.12, end=nxt - 0.08, words=ws, lines=lines, font=fnt))
    return out


PHRASES = _phrases()


def captions(cv, n):
    t = n / FPS
    ctx = cv.ctx
    # the scrap, lifted a touch off the page, with two bits of tape
    cv.shape_shadow(SCRAP_EDGE, dx=6, dy=10, blur=18, color=(60, 40, 20, 0.22))
    vb.paths.draw(cv, SCRAP_EDGE, '#fbf7ec', fill=True)
    for x, y, a in ((SCRAP.x + 40, SCRAP.y - 6, -0.5), (SCRAP.right - 40, SCRAP.y - 2, 0.45)):
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(a)
        ctx.rectangle(-55, -18, 110, 36)
        ctx.set_source_rgba(0.88, 0.82, 0.62, 0.62)
        ctx.fill()
        ctx.restore()
    ph = next((p for p in PHRASES if p['start'] <= t < p['end']), None)
    if ph is None:
        return
    fade = min(vb.clamp01((t - ph['start']) / 0.12), vb.clamp01((ph['end'] - t) / 0.12))
    fnt, lines = ph['font'], ph['lines']
    lh = text.line_height(fnt)
    y0 = SCRAP.cy - lh * len(lines) / 2 + 2
    ws = iter(ph['words'])
    left_edge, right_edge = 1e9, 0
    for i, line in enumerate(lines):
        lw = text.measure(line, fnt)
        x = SCRAP.cx - lw / 2
        left_edge, right_edge = min(left_edge, x), max(right_edge, x + lw)
        pos = 0
        for word in line.split(' '):
            w = next(ws, None)
            spoken = w is not None and t >= w.start
            sp.pencil_text(cv, word, fnt, x + text.measure(line[:pos], fnt), y0 + i * lh, GRAPHITE,
                           (1.0 if spoken else 0.42) * fade)
            pos += len(word) + 1
    cv.mark('caption', SCRAP.x, SCRAP.y, SCRAP.w, SCRAP.h)


# ---- the frame ----
def draw(n, cv):
    cv._sb_n = n
    ctx = cv.ctx
    ctx.set_source_surface(sp.backdrop(cv.width, cv.height), 0, 0)
    ctx.paint()
    if n < 357:
        if n < ERASE1 + 95:
            chart_scene(cv, n)
        if n >= ERASE0:
            fund_scene(cv, n)
    else:
        bars_scene(cv, n)
    draw_tool(cv, n)
    captions(cv, n)


# The callout is an annotation on the chart, meant to sit on it.
OVERLAP_OK = {('chart', 'callout')}

FILM = vb.Film(
    draw=draw,
    timeline=TIMELINE,
    formats=('9x16',),
    background='#f2ebd8',
    sounds=(VOICE.sound(at=0, fps=FPS),),
)

if __name__ == '__main__':
    vb.main(__file__)
