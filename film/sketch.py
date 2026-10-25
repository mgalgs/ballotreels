"""A pencil-on-paper kit for the sketchbook measure template (film/measure.py).

Copied from the approved style mock (film/mocks/sketchbook_pencil.py) and
extended with the pieces the template needs on top: `Item`, one mark drawn
on between two frames with a pencil tip to follow; `Rub`, an eraser pass
that rubs a set of items out and leaves a ghost and a smudge; and a backdrop
that lays out in any frame size.

Everything here is geometry baked once at import (seeded, so every frame
draws the same wobble) plus a few draw calls that take a progress 0..1:

- `Stroke`: one pencil line built from a few light overlapping passes, each
  with its own wobble and a little overshoot at the ends.
- `Hatch`: parallel pencil flicks filling a polygon, laid down in order.
- `ink(colour, alpha)`: a grainy cairo source, so lines and lettering pick
  up the paper's tooth instead of printing flat.
- `pencil_text`: lettering drawn through that grain.
- `backdrop()`: the cream grid page, its grain and its spiral binding.
- `draw_pencil`, `draw_eraser`: the tools themselves, drawn in code.
"""
import math
import random
from functools import lru_cache

import cairo
import numpy as np

import videobuilder as vb
from videobuilder import paths, text

GRAPHITE = (58, 55, 52)
ORANGE = (214, 118, 38)   # the one coloured pencil
PAPER = (242, 235, 216)
GRID = (176, 164, 136)


# ---- grainy ink ----
_BUFFERS = []


@lru_cache(maxsize=64)
def _ink_surface(colour, alpha, seed=7, size=192):
    rng = np.random.default_rng(seed)
    tooth = rng.random((size, size))
    # A pencil skips over the paper's tooth: mostly solid, a scatter of pale specks.
    a = np.clip(0.5 + 0.7 * tooth ** 0.55, 0, 1) * alpha
    r, g, b = (c / 255 for c in colour)
    px = np.empty((size, size, 4), np.uint8)
    px[..., 0] = (b * a * 255).astype(np.uint8)
    px[..., 1] = (g * a * 255).astype(np.uint8)
    px[..., 2] = (r * a * 255).astype(np.uint8)
    px[..., 3] = (a * 255).astype(np.uint8)
    data = bytearray(px.tobytes())
    surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, size, size, size * 4)
    _BUFFERS.append(data)  # cairo borrows the buffer; keep it alive
    return surf


def ink(colour, alpha=1.0):
    """A repeating grainy cairo pattern of `colour` (0-255 RGB) at `alpha`."""
    pat = cairo.SurfacePattern(_ink_surface(tuple(colour), round(alpha, 2)))
    pat.set_extend(cairo.EXTEND_REPEAT)
    pat.set_filter(cairo.FILTER_NEAREST)
    return pat


def _path(ctx, pts):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)


# ---- strokes ----
def _normals(pts):
    out = []
    for i in range(len(pts)):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1
        out.append((-dy / d, dx / d))
    return out


class Stroke:
    """One sketched line: `passes` light pencil passes along `pts`, each with
    its own seeded wobble (`wobble` px), a slight offset and an overshoot of up
    to `overshoot` px past each end, as a quick hand draws it."""

    def __init__(self, pts, seed, passes=2, wobble=1.6, width=3.4, overshoot=7.0,
                 alpha=0.8, step=5.0, closed=False):
        pts = list(pts) + ([pts[0]] if closed else [])
        rnd = random.Random(seed)
        n = max(2, int(paths.length(pts) / step) + 1)
        base = paths.resample(pts, n)
        nrm = _normals(base)
        self.passes = []
        for i in range(passes):
            f1, f2 = rnd.uniform(0.008, 0.02), rnd.uniform(0.03, 0.06)
            p1, p2 = rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)
            shift = rnd.uniform(-1, 1) * wobble * 0.8
            line = []
            for k, ((x, y), (nx, ny)) in enumerate(zip(base, nrm)):
                s = k * step
                o = shift + wobble * (0.7 * math.sin(s * f1 + p1) + 0.3 * math.sin(s * f2 + p2))
                line.append((x + nx * o, y + ny * o))
            if not closed and len(line) >= 2:
                line = _extend(line, overshoot * rnd.uniform(0.2, 1.0), overshoot * rnd.uniform(0.2, 1.0))
            w = width * rnd.uniform(0.7, 1.05) * (1.0 if i == 0 else 0.8)
            a = alpha * (1.0 if i == 0 else rnd.uniform(0.45, 0.7))
            self.passes.append((line, w, a))

    def draw(self, cv, p, colour=GRAPHITE, alpha=1.0):
        if p <= 0:
            return
        ctx = cv.ctx
        ctx.save()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        for i, (line, w, a) in enumerate(self.passes):
            # later passes trail the first a little, as a pencil goes back over a line
            q = vb.clamp01(p * (1 + 0.12 * i) - 0.12 * i)
            pts = paths.reveal(line, q)
            if len(pts) < 2:
                continue
            ctx.new_path()
            _path(ctx, pts)
            ctx.set_line_width(w)
            ctx.set_source(ink(colour, a * alpha))
            ctx.stroke()
        ctx.restore()

    def head(self, p):
        pts = paths.reveal(self.passes[0][0], p)
        return pts[-1] if pts else self.passes[0][0][0]


def _extend(line, a, b):
    (x0, y0), (x1, y1) = line[0], line[1]
    d = math.hypot(x1 - x0, y1 - y0) or 1
    start = (x0 - (x1 - x0) / d * a, y0 - (y1 - y0) / d * a)
    (x0, y0), (x1, y1) = line[-1], line[-2]
    d = math.hypot(x1 - x0, y1 - y0) or 1
    end = (x0 - (x1 - x0) / d * b, y0 - (y1 - y0) / d * b)
    return [start] + line + [end]


# ---- hatching ----
class Hatch:
    """Parallel pencil flicks across a polygon at `angle` (degrees), `spacing`
    px apart, each a little long or short at its ends and slightly bowed.
    `cross` adds a second layer at right angles."""

    def __init__(self, poly, seed, angle=45, spacing=14, cross=False, width=2.2,
                 alpha=0.55, inset=3):
        rnd = random.Random(seed)
        self.width, self.alpha = width, alpha
        self.lines = []
        for ang in ([angle, angle - 90] if cross else [angle]):
            self.lines += _hatch(poly, math.radians(ang), spacing, rnd, inset)
        # lay the flicks down left to right, the way a hand moves across
        self.lines.sort(key=lambda ln: min(ln[0][0], ln[-1][0]))

    def draw(self, cv, p, colour=GRAPHITE, alpha=1.0):
        if p <= 0 or not self.lines:
            return
        k = p * len(self.lines)
        ctx = cv.ctx
        ctx.save()
        ctx.new_path()
        for i, ln in enumerate(self.lines):
            if i >= k:
                break
            seg = ln if i + 1 <= k else paths.reveal(ln, k - i)
            if len(seg) >= 2:
                _path(ctx, seg)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(self.width)
        ctx.set_source(ink(colour, self.alpha * alpha))
        ctx.stroke()
        ctx.restore()

    def head(self, p):
        if not self.lines:
            return (0, 0)
        i = min(len(self.lines) - 1, int(p * len(self.lines)))
        return self.lines[i][-1]


def _hatch(poly, a, spacing, rnd, inset):
    ca, sa = math.cos(a), math.sin(a)
    # rotate the polygon so the hatch lines run horizontally
    rot = [(x * ca + y * sa, -x * sa + y * ca) for x, y in poly]
    ys = [p[1] for p in rot]
    out = []
    y = min(ys) + spacing * rnd.uniform(0.3, 0.8)
    flip = False
    while y < max(ys):
        xs = []
        for (x0, y0), (x1, y1) in zip(rot, rot[1:] + rot[:1]):
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) / (y1 - y0) * (x1 - x0))
        xs.sort()
        for xa, xb in zip(xs[::2], xs[1::2]):
            xa += inset + rnd.uniform(-2, 5)
            xb -= inset + rnd.uniform(-2, 5)
            if xb - xa < 6:
                continue
            yy = y + rnd.uniform(-1.5, 1.5)
            bow = rnd.uniform(-1.6, 1.6)
            tilt = rnd.uniform(-1.5, 1.5)
            seg = [(xa, yy - tilt), ((xa + xb) / 2, yy + bow), (xb, yy + tilt)]
            seg = [(u * ca - v * sa, u * sa + v * ca) for u, v in seg]
            out.append(seg[::-1] if flip else seg)
            flip = not flip
        y += spacing * rnd.uniform(0.85, 1.15)
    return out


# ---- lettering ----
def pencil_text(cv, lines, font, x, y, colour=GRAPHITE, alpha=1.0, align='left', width=None):
    """`text.draw` through the pencil grain. Returns the Box drawn."""
    ctx = cv.ctx
    ctx.push_group()
    box = text.draw(cv, lines, font, x, y, '#000000', align=align, width=width)
    mask = ctx.pop_group()
    ctx.set_source(ink(colour, alpha))
    ctx.mask(mask)
    return box


# ---- shapes ----
def ellipse(cx, cy, rx, ry, a0=0.0, a1=2 * math.pi, rot=0.0, n=64):
    cr, sr = math.cos(rot), math.sin(rot)
    out = []
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return out


def catmull(pts, per=16):
    """A smooth curve through `pts` (Catmull-Rom), `per` samples a span."""
    out = []
    p = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t
                                    + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)
                             for j in range(2)))
    out.append(pts[-1])
    return out


def dashes(pts, dash=18, gap=12):
    """An open path cut into dash point lists, `dash` px on, `gap` px off."""
    total = paths.length(pts)
    n = max(2, int(total / 2) + 2)
    r = paths.resample(pts, n)
    step = total / (n - 1)
    out, s = [], 0.0
    while s < total:
        i0, i1 = int(s / step), min(n - 1, int((s + dash) / step))
        if i1 > i0:
            out.append(r[i0:i1 + 1])
        s += dash + gap
    return out


# ---- the page ----
@lru_cache(maxsize=4)
def backdrop(w, h):
    """The notebook page as a cached cairo surface: cream paper, a faint grid,
    grain, a soft vignette and spiral binding across the top."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(*(c / 255 for c in PAPER))
    ctx.paint()
    # faint grid, 5 mm squares
    cell = 60
    ctx.set_line_width(1.6)
    ctx.set_source_rgba(*(c / 255 for c in GRID), 0.32)
    x = (w % cell) / 2
    while x < w:
        ctx.move_to(x, 0)
        ctx.line_to(x, h)
        x += cell
    y = 180
    while y < h:
        ctx.move_to(0, y)
        ctx.line_to(w, y)
        y += cell
    ctx.stroke()
    # paper tooth
    ctx.set_source(vb.paper_grain(w, h, seed=3))
    ctx.set_operator(cairo.OPERATOR_SOFT_LIGHT)
    ctx.paint_with_alpha(0.55)
    ctx.set_operator(cairo.OPERATOR_OVER)
    # vignette, warm
    g = cairo.RadialGradient(w / 2, h * 0.45, h * 0.3, w / 2, h * 0.5, h * 0.75)
    g.add_color_stop_rgba(0, 0.35, 0.25, 0.12, 0)
    g.add_color_stop_rgba(1, 0.35, 0.25, 0.12, 0.22)
    ctx.set_source(g)
    ctx.paint()
    # spiral binding: punched holes and wire loops
    pitch = 72
    for i in range(int(w / pitch) + 1):
        cx = pitch / 2 + i * pitch
        ctx.arc(cx, 96, 15, 0, 2 * math.pi)
        ctx.set_source_rgb(0.2, 0.17, 0.15)
        ctx.fill()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for dx, col, lw in ((3, (0, 0, 0, 0.25), 9), (0, (0.42, 0.41, 0.4, 1), 8), (-1.5, (0.75, 0.74, 0.72, 1), 3)):
            ctx.new_path()
            ctx.move_to(cx - 6 + dx, 100)
            ctx.curve_to(cx - 18 + dx, 60, cx - 22 + dx, 20, cx - 4 + dx, -10)
            ctx.set_source_rgba(*col)
            ctx.set_line_width(lw)
            ctx.stroke()
    return surf


# ---- the tools ----
def _poly(ctx, pts):
    ctx.new_path()
    _path(ctx, pts)
    ctx.close_path()


def draw_pencil(cv, x, y, colour=None, lift=0.0, angle=-0.72):
    """A pencil, tip at (x, y), body up and to the right. `colour` None is a
    yellow graphite pencil; an RGB tuple paints a coloured pencil that colour.
    `lift` 0..1 raises it off the page (a bigger, softer shadow)."""
    ctx = cv.ctx
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(angle)
    s = 1 + 0.05 * lift
    ctx.scale(s, s)
    half, L = 19, 470
    body = (232, 178, 64) if colour is None else colour
    lead = GRAPHITE if colour is None else colour
    # shadow
    ctx.save()
    sx, sy = 10 + 30 * lift, 16 + 34 * lift
    ctx.rotate(-angle)
    ctx.translate(sx, sy)
    ctx.rotate(angle)
    _poly(ctx, [(0, 0), (64, -half), (L, -half), (L, half), (64, half)])
    ctx.set_source_rgba(0.2, 0.14, 0.08, 0.16 - 0.06 * lift)
    ctx.fill()
    ctx.restore()
    # sharpened wood
    _poly(ctx, [(0, 0), (64, -half), (64, half)])
    ctx.set_source_rgb(0.9, 0.78, 0.6)
    ctx.fill()
    # lead
    _poly(ctx, [(0, 0), (20, -6), (20, 6)])
    ctx.set_source_rgb(*(c / 255 for c in lead))
    ctx.fill()
    # painted body, three facets
    r, g, b = (c / 255 for c in body)
    for y0, y1, k in ((-half, -half / 3, 1.12), (-half / 3, half / 3, 1.0), (half / 3, half, 0.8)):
        ctx.new_path()
        ctx.move_to(62, y0)
        for t in range(4):
            yy = y0 + (y1 - y0) * t / 3
            ctx.line_to(62 - 4 * math.sin(t * 1.4), yy)
        ctx.line_to(L - 70, y1)
        ctx.line_to(L - 70, y0)
        ctx.close_path()
        ctx.set_source_rgb(min(1, r * k), min(1, g * k), min(1, b * k))
        ctx.fill()
    # ferrule and eraser
    ctx.rectangle(L - 70, -half, 42, 2 * half)
    lg = cairo.LinearGradient(0, -half, 0, half)
    lg.add_color_stop_rgb(0, 0.86, 0.85, 0.82)
    lg.add_color_stop_rgb(0.4, 0.66, 0.65, 0.62)
    lg.add_color_stop_rgb(1, 0.45, 0.44, 0.42)
    ctx.set_source(lg)
    ctx.fill()
    ctx.rectangle(L - 28, -half + 1, 28, 2 * half - 2)
    ctx.set_source_rgb(0.86, 0.82, 0.74)
    ctx.fill()
    # outline
    _poly(ctx, [(0, 0), (64, -half), (L, -half), (L, half), (64, half)])
    ctx.set_source_rgba(0.15, 0.12, 0.1, 0.55)
    ctx.set_line_width(2)
    ctx.stroke()
    ctx.restore()


def draw_eraser(cv, x, y, angle=-0.35):
    """A block eraser centred on (x, y), with a card sleeve."""
    ctx = cv.ctx
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(angle)
    w, h = 200, 92
    ctx.save()
    ctx.translate(14, 18)
    _round(ctx, -w / 2, -h / 2, w, h, 12)
    ctx.set_source_rgba(0.2, 0.14, 0.08, 0.16)
    ctx.fill()
    ctx.restore()
    _round(ctx, -w / 2, -h / 2, w, h, 12)
    ctx.set_source_rgb(0.95, 0.93, 0.88)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.15, 0.12, 0.1, 0.5)
    ctx.set_line_width(2)
    ctx.stroke()
    ctx.rectangle(-w / 2 + 70, -h / 2 - 2, w - 70, h + 4)
    ctx.set_source_rgb(0.84, 0.6, 0.3)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.15, 0.12, 0.1, 0.5)
    ctx.stroke()
    ctx.restore()


def _round(ctx, x, y, w, h, r):
    ctx.new_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


# ---- things drawn on between two frames ----
DRAW = vb.bezier(0.42, 0, 0.3, 1)   # a hand: starts deliberately, eases into the end


class Item:
    """One mark on the page, drawn on from frame `f0` to `f1`. `draw(cv, p)`
    draws it at progress p (0..1); `head(p)` is where the pencil tip is (None:
    no pencil follows it, e.g. a fade or shading laid in behind the line);
    `ink` the pencil's colour. `at` = (x, y, angle) draws it rotated by
    `angle` about (x, y), its points given in that rotated space."""

    def __init__(self, f0, f1, draw, head=None, ink=GRAPHITE, ease=DRAW, at=None):
        self.f0, self.f1 = f0, max(f0 + 1, f1)
        self._draw, self._head, self.ink, self.ease, self.at = draw, head, ink, ease, at

    def p(self, n):
        return self.ease(vb.clamp01((n - self.f0) / (self.f1 - self.f0)))

    def draw(self, cv, n, full=False):
        p = 1.0 if full else self.p(n)
        if p <= 0:
            return
        if self.at is None:
            self._draw(cv, p)
            return
        x, y, a = self.at
        ctx = cv.ctx
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(a)
        self._draw(cv, p)
        ctx.restore()

    def head(self, n):
        if not self._head:
            return None
        hx, hy = self._head(self.p(n))
        if self.at is None:
            return hx, hy
        x, y, a = self.at
        ca, sa = math.cos(a), math.sin(a)
        return x + hx * ca - hy * sa, y + hx * sa + hy * ca


def stroke_item(f0, f1, stroke, ink=GRAPHITE, alpha=1.0, pencil=True, at=None):
    return Item(f0, f1, lambda cv, p: stroke.draw(cv, p, ink, alpha),
                stroke.head if pencil else None, ink, at=at)


def hatch_item(f0, f1, hatch, ink=GRAPHITE, alpha=1.0, pencil=True, at=None):
    return Item(f0, f1, lambda cv, p: hatch.draw(cv, p, ink, alpha),
                hatch.head if pencil else None, ink, ease=vb.linear, at=at)


def text_item(f0, f1, words, fnt, x, y, ink=GRAPHITE, alpha=1.0, align='left', pencil=True,
              at=None):
    """One line of lettering written on left to right. `x` is the left edge,
    or the centre / right edge for align 'center' / 'right'; `y` the top."""
    w = text.measure(words, fnt)
    h = text.line_height(fnt)
    left = {'left': x, 'center': x - w / 2, 'right': x - w}[align]

    def draw(cv, p):
        if p >= 1:
            pencil_text(cv, words, fnt, left, y, ink, alpha)
            return
        with cv.clip(left - 30, y - 40, 30 + (w + 60) * p, h + 80):
            pencil_text(cv, words, fnt, left, y, ink, alpha)

    def head(p):
        return (left + w * p, y + h * (0.62 + 0.12 * math.sin(p * w / 16)))

    it = Item(f0, f1, draw, head if pencil else None, ink, ease=vb.linear, at=at)
    it.box = (left, y, w, h)
    return it


def fade_item(f0, f1, draw):
    """Something laid down whole rather than drawn (a paper scrap, tape): it
    drops onto the page over f0..f1, settling from a touch larger."""
    def d(cv, p):
        with cv.layer(opacity=p):
            draw(cv)
    return Item(f0, f1, d, None, ease=vb.ease_out_quint)


# ---- the eraser ----
ERASER_W = 190


def zigzag(box, width=ERASER_W):
    """The eraser's path over `box` = (x, y, w, h): side to side, top to bottom,
    rows close enough that its `width` covers everything between them."""
    x, y, w, h = box
    rows = max(1, math.ceil(h / (width * 0.62)))
    pts = []
    for i in range(rows + 1):
        yy = y + h * i / rows
        a, b = (x - 20, x + w + 20) if i % 2 == 0 else (x + w + 20, x - 20)
        pts += [(a, yy), (b, yy + width * 0.2)]
    return catmull(pts, per=6)


GHOST = 0.18      # how much of a rubbed-out mark is left at first
GHOST_FADE = 40   # frames for the ghost to fade away


class Rub:
    """An eraser pass over `box` from frame `e0` to `e1`, rubbing out
    `items`. Before `e0` the items draw as usual; after, a ghost of them and
    a smudge fade away over GHOST_FADE frames."""

    def __init__(self, items, e0, e1, box, seed, width=ERASER_W):
        self.items, self.e0, self.e1, self.box, self.seed = items, e0, e1, box, seed
        self.width = width
        self.path = zigzag(box, width)

    @property
    def gone(self):
        return math.inf if self.e1 is None else self.e1 + GHOST_FADE

    def draw(self, cv, n, mark=None):
        if self.e0 is None or n < self.e0:
            for it in self.items:
                it.draw(cv, n)
            if mark:
                mark()
            return
        if n >= self.gone:
            return
        e = vb.clamp01((n - self.e0) / max(1, self.e1 - self.e0))
        ctx = cv.ctx
        ctx.push_group()
        for it in self.items:
            it.draw(cv, n, full=n >= self.e1 or it.f1 <= self.e0)
        rubbed = paths.reveal(self.path, e)
        ctx.set_operator(cairo.OPERATOR_DEST_OUT)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        if len(rubbed) >= 2:
            ctx.new_path()
            _path(ctx, rubbed)
            ctx.set_line_width(self.width)
            ctx.set_source_rgba(0, 0, 0, 1 - GHOST)
            ctx.stroke()
        ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.pop_group_to_source()
        ghost = 1.0 if n < self.e1 else vb.interpolate(n, [self.e1, self.gone], [1, 0])
        ctx.paint_with_alpha(ghost)
        smudge = vb.clamp01(e * 1.2) * ghost
        if smudge > 0:
            surf, ox, oy = smudge_surface(tuple(round(v) for v in self.box), self.width, self.seed)
            ctx.set_source_surface(surf, ox, oy)
            ctx.paint_with_alpha(smudge)

    def tool(self, n):
        """(x, y, angle) of the eraser at frame n, or None when it's not rubbing."""
        if self.e0 is None or not self.e0 <= n < self.e1:
            return None
        e = vb.clamp01((n - self.e0) / max(1, self.e1 - self.e0))
        rubbed = paths.reveal(self.path, e)
        x, y = rubbed[-1] if rubbed else self.path[0]
        return x, y + 10 * math.sin(n * 1.7), -0.3 + 0.12 * math.sin(n * 0.9)


_SMUDGES = {}


def smudge_surface(box, width, seed):
    """The grey smear an eraser leaves along its path over `box`: (surface, x, y)."""
    key = (box, width, seed)
    if key not in _SMUDGES:
        from PIL import Image, ImageDraw, ImageFilter
        x, y, w, h = box
        pad = width
        img = Image.new('L', (int(w + 2 * pad), int(h + 2 * pad)), 0)
        d = ImageDraw.Draw(img)
        rnd = random.Random(seed)
        pts = paths.resample(zigzag(box, width), 60)
        r0 = width / 190
        for px, py in pts:
            r = rnd.uniform(30, 70) * r0
            cx, cy = px - x + pad, py - y + pad
            d.ellipse([cx - r * 1.6, cy - r * 0.5, cx + r * 1.6, cy + r * 0.5], fill=rnd.randint(20, 46))
        img = img.filter(ImageFilter.GaussianBlur(26 * r0))
        a = np.asarray(img).astype('float32') / 255
        grey = 70 / 255
        px = np.empty(a.shape + (4,), np.uint8)
        px[..., 0] = px[..., 1] = px[..., 2] = (grey * a * 255).astype(np.uint8)
        px[..., 3] = (a * 255).astype(np.uint8)
        data = bytearray(px.tobytes())
        surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, img.width, img.height,
                                                  img.width * 4)
        _BUFFERS.append(data)
        _SMUDGES[key] = (surf, x - pad, y - pad)
    return _SMUDGES[key]
