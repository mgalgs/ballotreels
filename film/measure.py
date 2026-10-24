"""The measure video template (one for every measure contest, STANDARD.md 2.1).

    BALLOTREELS_CONTEST=data/ca-2026-11-03/prop-2 python film/measure.py preview
    PYTHONPATH=$VB python film/measure.py sheet --format all
    python -m ballotreels render data/ca-2026-11-03/prop-2 --format all

Reads BALLOTREELS_CONTEST for which contest to render (default: the Prop 2
contest, so the authoring-loop tools work with no setup); nothing about any
one contest is hard-coded. Cuts come from the narration audio's own phrase
times, not a music grid, so the grid is set to one frame per beat
(`GRID.b(beat) == beat` for any integer frame number) and every segment's
`at`/`until` is literally a frame number.
"""
import math
import os
import sys
from bisect import bisect_right
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import videobuilder as vb  # noqa: E402
from videobuilder import Box, per_format, text  # noqa: E402

from ballotreels.contest import load_contest  # noqa: E402
from ballotreels.narration import match_phrases, section_order  # noqa: E402

# ---- assets: vendored font, with its licence, in assets/ ----
for _f in sorted((HERE / 'assets').rglob('*.[ot]tf')):
    text.register(_f)
FAMILY = 'Inter'

FPS = 30
# One frame per beat: our cuts land on exact narration frames, never on a
# music grid (there is no music; STANDARD.md 4.2), so "beats" here just mean
# frame numbers, and the half-beat-grid rule is trivially satisfied.
GRID = vb.Grid(fps=FPS, bpm=FPS * 60)


def fr(seconds):
    return vb.round_half_up(seconds * FPS)


# ---- contest data: nothing below this point is specific to one contest ----
CONTEST_DIR = Path(os.environ.get(
    'BALLOTREELS_CONTEST', str(REPO_ROOT / 'data' / 'ca-2026-11-03' / 'prop-2')))
CONTEST = load_contest(CONTEST_DIR)
VOICE = vb.speech.load(CONTEST_DIR / 'narration.wav')
CAPTIONS_TRACK = VOICE.track_at(0, FPS)

SPANS = match_phrases(CONTEST)
if SPANS is None:
    raise RuntimeError(f'{CONTEST_DIR}: no narration sidecars; run '
                       f'`python -m ballotreels narration` then `videobuilder say` first')
SECTION_IDS = section_order(CONTEST)
SECTIONS_BY_ID = {s.id: s for s in CONTEST.script.sections}
LINES_BY_KEY = {(s.id, i): line for s in CONTEST.script.sections
                for i, line in enumerate(s.lines)}
SECTION_STARTS = [fr(next(s.start for s in SPANS if s.section == sid))
                  for sid in SECTION_IDS]
SECTION_STARTS[0] = 0  # the film itself starts at frame 0, not the first word's
VOICE_FRAMES = VOICE.frames(FPS)
# A brief hold on the last section's last caption before the hard cut to the
# sources card, so it isn't cut the instant the narration stops.
END_HOLD_FRAMES = fr(0.5)
NARRATION_END_FRAMES = VOICE_FRAMES + END_HOLD_FRAMES
SECTION_ENDS = SECTION_STARTS[1:] + [NARRATION_END_FRAMES]


def _source_card_seconds(contest):
    """Read time for the closing sources card: 1 s plus its words at 3 words
    a second (the skill's read-time floor), with a few extra words a source
    for its URL, which reads slower than its word count."""
    words = sum(len(s.publisher.split()) + 3 for s in contest.sources)
    return 1 + words / 3.0


SOURCES_FRAMES = fr(_source_card_seconds(CONTEST))
TOTAL_FRAMES = NARRATION_END_FRAMES + SOURCES_FRAMES

SEGMENTS = []
for _i, _sid in enumerate(SECTION_IDS):
    _sec = SECTIONS_BY_ID[_sid]
    # The heading is shown only briefly (draw_heading), not for the whole
    # section, so it isn't counted toward the section's read time: the
    # captions (what's actually on screen for the rest of it) are.
    _copy = [l.text for l in _sec.lines]
    SEGMENTS.append(vb.Segment(_sid, SECTION_STARTS[_i], SECTION_ENDS[_i],
                               data={'copy': _copy, 'heading': _sec.heading,
                                     'section_index': _i}))
SOURCES_HEADING = 'Sources'
SEGMENTS.append(vb.Segment(
    'sources', NARRATION_END_FRAMES, TOTAL_FRAMES,
    data={'copy': [f'{s.publisher}: {s.url}' for s in CONTEST.sources]}))
TIMELINE = vb.Timeline(GRID, SEGMENTS, end=TOTAL_FRAMES)

_LINE_STARTS = [s.start for s in SPANS]


def active_line_at(t):
    """The NarrationSpan spoken at second `t`, or None in a silence."""
    i = bisect_right(_LINE_STARTS, t) - 1
    if i < 0:
        return None
    span = SPANS[i]
    return span if span.start <= t <= span.end else None


def attribution_text(span):
    """The publisher(s) a spoken line cites, or None (connective lines, and
    silences, show no attribution)."""
    if span is None:
        return None
    line = LINES_BY_KEY[(span.section, span.index)]
    if line.connective or not line.sources:
        return None
    seen = []
    for sid in line.sources:
        src = CONTEST.source(sid)
        if src and src.publisher not in seen:
            seen.append(src.publisher)
    return '  ·  '.join(seen) if seen else None


# ---- look: one neutral palette, one typeface (STANDARD.md 4.1) ----
BG = '#14181c'
INK = '#f4f4f1'
MUTED = '#9aa0a6'
ACCENT = '#c9a227'  # gold: not a party colour, not red/blue, not red/green


def font(size, weight=400, **kw):
    return vb.Font(FAMILY, size, weight=weight, **kw)


def layout_9x16():
    frame = Box(0, 0, 1080, 1920)
    safe = frame.pad(80, 64, 260, 64)
    title_box = Box(safe.x, safe.y, safe.w, 72)
    progress_box = Box(safe.x, title_box.bottom + 16, safe.w, 20)
    heading_box = Box(safe.x, progress_box.bottom + 28, safe.w, 230)
    attribution_box = Box(safe.x, heading_box.bottom + 14, safe.w, 88)
    sources_box = Box(safe.x, heading_box.y, safe.w, safe.bottom - heading_box.y)
    return dict(
        safe=safe, title_box=title_box, progress_box=progress_box,
        heading_box=heading_box, attribution_box=attribution_box,
        captions_safe=safe, sources_box=sources_box, sources_cols=1, gap=28,
        title_font=font(26, 600), heading_font=font(56, 700, line_height=1.08),
        attribution_font=font(28, 500), caption_font=font(60, 800),
        sources_heading_font=font(52, 700), source_font=font(32, 600),
        source_url_font=font(24, 400), dot=16,
    )


def layout_16x9():
    frame = Box(0, 0, 1920, 1080)
    safe = frame.pad(56, 150, 70, 150)
    title_box = Box(safe.x, safe.y, safe.w, 46)
    progress_box = Box(safe.x, title_box.bottom + 10, safe.w, 16)
    heading_box = Box(safe.x, progress_box.bottom + 18, safe.w, 130)
    attribution_box = Box(safe.x, heading_box.bottom + 8, safe.w, 54)
    sources_box = Box(safe.x, heading_box.y, safe.w, safe.bottom - heading_box.y)
    return dict(
        safe=safe, title_box=title_box, progress_box=progress_box,
        heading_box=heading_box, attribution_box=attribution_box,
        captions_safe=safe, sources_box=sources_box, sources_cols=2, gap=36,
        title_font=font(22, 600), heading_font=font(46, 700, line_height=1.08),
        attribution_font=font(23, 500), caption_font=font(52, 800),
        sources_heading_font=font(44, 700), source_font=font(28, 600),
        source_url_font=font(21, 400), dot=13,
    )


LAYOUTS = {'9x16': layout_9x16(), '16x9': layout_16x9()}

SETTLE = vb.critical(170)
ENTER = 3


# ---- helpers ----
def centered_block(cv, box, words, fnt, colour, valign='top'):
    lines = text.wrap(words, fnt, box.w, balance=True)
    w, h = text.block_size(lines, fnt)
    at = box.anchor(box.w, h, {'top': 'top', 'center': 'center', 'bottom': 'bottom'}[valign])
    return text.draw(cv, lines, fnt, at.x, at.y, colour, align='center', width=at.w)


def draw_title(cv, L):
    drawn = centered_block(cv, L['title_box'], CONTEST.title, L['title_font'], MUTED)
    cv.mark('title', *drawn)


def draw_progress(cv, L, index):
    box = L['progress_box']
    n = len(SECTION_IDS)
    d = L['dot']
    gap = max(d, (box.w - d * n) / max(1, n - 1)) if n > 1 else 0
    gap = min(gap, 28)
    total_w = d * n + gap * (n - 1)
    x0 = box.x + (box.w - total_w) / 2
    y = box.cy
    for i in range(n):
        cx = x0 + i * (d + gap)
        cv.rect(cx, y - d / 2, d, d, ACCENT if i == index else MUTED,
               radius=d / 2, alpha=1 if i == index else 0.5)
    cv.mark('progress', x0, y - d / 2, total_w, d)


def draw_heading(cv, shot, L):
    f = shot.f
    hold, fade = int(1.6 * FPS), int(0.4 * FPS)
    if f > hold + fade:
        return
    s = min(1, vb.spring_at(f + ENTER, FPS, **SETTLE))
    opacity = s if f <= hold else s * vb.clamp01(1 - (f - hold) / fade)
    if opacity <= 0:
        return
    with cv.layer(opacity=opacity, dy=(1 - s) * 24):
        drawn = centered_block(cv, L['heading_box'], shot.data['heading'],
                               L['heading_font'], INK, valign='top')
        cv.mark('heading', *drawn)


def draw_attribution(cv, L, span):
    pub = attribution_text(span)
    if not pub:
        return
    drawn = centered_block(cv, L['attribution_box'], pub, L['attribution_font'], MUTED)
    cv.mark('attribution', *drawn)


def section_scene(cv, n, shot, L):
    draw_progress(cv, L, shot.data['section_index'])
    draw_heading(cv, shot, L)
    t = n / FPS
    draw_attribution(cv, L, active_line_at(t))
    vb.captions.draw(cv, CAPTIONS_TRACK, t, font=L['caption_font'], safe=L['captions_safe'],
                     color=INK, spoken=ACCENT, box=BG, box_alpha=0.78)


def sources_scene(cv, shot, L):
    box = L['sources_box']
    s = min(1, vb.spring_at(shot.f + ENTER, FPS, **SETTLE))
    with cv.layer(opacity=s, dy=(1 - s) * 24):
        heading = text.draw(cv, text.wrap(SOURCES_HEADING, L['sources_heading_font'], box.w, balance=True),
                            L['sources_heading_font'], box.x, box.y, INK, align='center', width=box.w)
        cv.mark('sources-heading', *heading)
        list_box = Box(box.x, heading.bottom + L['gap'], box.w, box.bottom - heading.bottom - L['gap'])
        cols = L['sources_cols']
        rows = math.ceil(len(CONTEST.sources) / cols)
        cells = list_box.grid(cols, rows, gap=L['gap'])
        for i, src in enumerate(CONTEST.sources):
            cell = cells[i]
            pub = text.draw(cv, text.wrap(src.publisher, L['source_font'], cell.w, balance=True),
                            L['source_font'], cell.x, cell.y, INK, width=cell.w)
            url = text.draw(cv, text.wrap(src.url, L['source_url_font'], cell.w, balance=False),
                            L['source_url_font'], cell.x, pub.bottom + 6, MUTED, width=cell.w)
            cv.mark(f'source-{i}', cell.x, cell.y, cell.w, url.bottom - cell.y)


def draw(n, cv):
    L = per_format(LAYOUTS, cv)
    shot = TIMELINE.live(n)[-1]
    draw_title(cv, L)
    if shot.name == 'sources':
        sources_scene(cv, shot, L)
    else:
        section_scene(cv, n, shot, L)


FILM = vb.Film(
    draw=draw,
    timeline=TIMELINE,
    formats=('9x16', '16x9'),
    background=BG,
    sounds=(VOICE.sound(at=0, fps=FPS),),
)

if __name__ == '__main__':
    vb.main(__file__)
