"""The state crash course film, template version 3 (ballotreels.crash_course).

    python -m ballotreels render data/ut-2026-11-03 --format 9x16
    python -m ballotreels render data/ut-2026-11-03 --format 16x9
    BALLOTREELS_CRASH_COURSE=data/ut-2026-11-03 python film/crash_course.py sheet

One video through every statewide measure on a state's ballot, in
contests.toml's order, that says nothing of its own: a contact sheet of
one-liners. It reads the election named by BALLOTREELS_CRASH_COURSE
(default: Utah's) and lays it out with ballotreels.crash_course.plan:

- an opening card, on screen only, with no narration: the state's name,
  how many statewide measures it has, and the election's date;
- pages of up to six tiles, a measure to a tile (2 columns by 3 rows in
  9:16, 3 by 2 in 16:9), each headed with the state's name and
  "statewide measures" ("1 of 3" when there are several). Each tile is
  drawn on, one at a time, while its one-liner is said: the measure's
  badge and number as its card draws them, its short title, its
  one-liner written out, and, small, where its own video is. The sound
  is the one-liner's cut of the measure's committed narration; the slot
  is that cut plus ballotreels.crash_course.SLOT_GAP_SECONDS, never
  padded out to match a longer one. Every tile is the same size, in the
  same type, drawn the same way. Earlier tiles stay up; the next page
  comes on clean;
- a closing page, still and silent, pointing to each measure's own
  video on the state's page;
- a sources card, in the measure film's style: what the one-liners
  cite, grouped under each measure's title, over as many pages as it
  takes.

The tile's words are its one-liner's own, so there is no caption. On
every frame, the link under the stage is the state's page
(ballotreels.org/<st>/<year>), where the crash course is shown.

Phone-first: 9:16 is the default format, and the only one the pipeline
renders. The 16:9 format, for YouTube, is rendered from the command line
only. It has the same frames, sound and chapters, laid out for
landscape: its sources pages are 9:16's pages (so each comes on at the
same moment), with two or more groups set in two columns. The drawing
sounds follow the 9x16 strokes, as the measure film's do.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _p in (REPO_ROOT, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import videobuilder as vb  # noqa: E402
from videobuilder import Box, text  # noqa: E402

import draw_sound as dsnd  # noqa: E402
import sketch as sp  # noqa: E402
from sketch import GRAPHITE, ORANGE, Stroke, stroke_item, text_item  # noqa: E402

from ballotreels import crash_course as cc  # noqa: E402
from ballotreels.ballots import badge, ballot_for, state_of  # noqa: E402
from ballotreels.site import pages  # noqa: E402
from ballotreels.site.config import DEFAULT_SITE_URL  # noqa: E402
from ballotreels.storyboard import SOURCES_CARD_SECONDS  # noqa: E402
from ballotreels.storyboard import frame as to_frame  # noqa: E402

MEASURE_FILM = HERE / 'measure.py'

# ---- the election ----
ELECTION_DIR = Path(os.environ.get(
    'BALLOTREELS_CRASH_COURSE', str(REPO_ROOT / 'data' / 'ut-2026-11-03')))
COURSE = cc.plan(ELECTION_DIR)
FPS = COURSE.fps
GRID = vb.Grid(fps=FPS, bpm=FPS * 60)  # one frame a beat, as the measure film

# the state's page on the site, where the crash course is shown, printed
# under the stage on every frame (in the measure films' own place)
SITE_URL = os.environ.get('BALLOTREELS_SITE_URL') or DEFAULT_SITE_URL
ABBR = state_of(COURSE.election.state) or COURSE.election.id[:2]
LINK = pages.display_url(SITE_URL, '/{}/{}'.format(ABBR, pages.election_year(COURSE.election.id)))


def load_template():
    """film/measure.py, loaded for the first member as its own render loads
    it: the template's helpers and layouts (the same in every member's
    film), with the link it prints swapped for the state page's."""
    member = COURSE.members[0]
    old = os.environ.get('BALLOTREELS_CONTEST')
    os.environ['BALLOTREELS_CONTEST'] = str(Path(member.contest.path).resolve())
    try:
        mod = vb.load_module(str(MEASURE_FILM))
    finally:
        if old is None:
            os.environ.pop('BALLOTREELS_CONTEST', None)
        else:
            os.environ['BALLOTREELS_CONTEST'] = old
    mod.LINK = LINK
    return mod


T = load_template()
# 9x16 first: the default, and the only one the pipeline renders; 16x9 is
# rendered from the command line (`render <election-dir> --format 16x9`)
FORMATS = ('9x16', '16x9')


# ---- the opening card: on screen only ----
def heading_items(L, words, f0, y, fnt=None):
    """A heading written on centred at `y`, underlined in the headings'
    orange, as the measure film's sources card heads itself."""
    fnt = fnt or L['heading_font']
    hb = L['heading']
    items, f, hbox = T.write_lines(f0, [words], fnt, hb.x, y, align='center', width=hb.w)
    w = text.measure(words, fnt)
    under = Stroke([(hb.cx - w / 2 - 6, hbox.bottom + 2), (hb.cx + w / 2 + 8, hbox.bottom + 4)],
                   T.seed_of('underline', words), passes=2, width=5 * L['u'])
    items.append(stroke_item(f + 1, f + 9, under, ORANGE))
    return items, f + 10, hbox


def opening_card(L):
    """The state's name, "N statewide measures" and the election's date,
    centred on the stage: words from the contest index, nothing else."""
    st = L['stage']
    u = L['u']
    big = T.font(L['heading_font'].size * 1.4, 700)
    mid = T.font(72 * u, family=T.PRINT)
    small = T.font(60 * u, family=T.PRINT)
    lh_big, lh_mid, lh_small = (text.line_height(f) for f in (big, mid, small))
    gap = 36 * u
    total = lh_big + 14 + gap + lh_mid + gap * 0.5 + lh_small
    y = st.y + (st.h - total) / 2
    items, f, hbox = heading_items(L, COURSE.state_name, 4, y, big)
    y = hbox.bottom + 14 + gap
    more, f, _ = T.write_lines(f, [COURSE.headline], mid, st.x, y, align='center', width=st.w)
    items += more
    y += lh_mid + gap * 0.5
    more, f, _ = T.write_lines(f + 2, [COURSE.date], small, st.x, y, align='center', width=st.w)
    items += more
    # all of it on, and the pencil gone, before the card's first second
    # is up: the web copy's poster is that frame (pipeline.encode)
    return T.scaled(items, 4, max(8, COURSE.opening // 2 - 10))


# ---- the pages of tiles ----
GRIDS = {'9x16': (2, 3), '16x9': (3, 2)}  # (columns, rows) of tiles on a page
TILE_GAP = 26    # px between two tiles, before L['u']
TILE_PAD = 20    # px inside a tile, around its contents
TITLE_LINES = 2  # a short title longer than this is cut, with an ellipsis
LINE_MAX = 54    # px, before L['u']: the one-liners' largest type
TILE_WRITE = 8   # frames into its slot the tile's one-liner starts writing
URL_ALPHA = 0.8  # the link's quiet graphite


def short_title(m):
    """The measure's title as contests.toml gives it, less its designation
    and number where the badge shows them: "Proposition 3: PROVIDES ..."
    -> "PROVIDES ..."."""
    head, colon, rest = m.entry.title.partition(':')
    return rest.strip() if colon and tile_badge(m) else m.entry.title


def tile_badge(m):
    """(designation, number) as the measure's card draws its badge, or None
    where the ballot numbers no measure."""
    card = m.contest.script.card
    if card is None or card.number is None:
        return None
    word = badge(ballot_for(m.contest.division), m.contest.title, card.number)
    return None if word is None else (word, card.number)


def tile_url(m):
    """Where the measure's own video is: its page's short path on the site."""
    return pages.display_url(SITE_URL, pages.contest_path(ABBR, COURSE.election.id, m.entry.id))


def page_head(L, k, of, f0):
    """A page's heading: the state's name, underlined, over "statewide
    measures", with "k of n" at its right when there are several pages.
    Returns (items, marks, the bottom of what it takes)."""
    hb = L['heading']
    items, f, hbox = heading_items(L, COURSE.state_name, f0, hb.y + 6)
    sub = T.font(48 * L['u'], family=T.PRINT)
    y = hbox.bottom + 14 * L['u']
    more, f, sbox = T.write_lines(f, ['statewide measures'], sub, hb.x, y, align='center', width=hb.w,
                                  speed=1.5)
    items += more
    if of > 1:
        nf = T.font(36 * L['u'], family=T.PRINT)
        more, _, _ = T.write_lines(f, [f'{k} of {of}'], nf, hb.x, y + text.line_height(sub) - text.line_height(nf),
                                   align='right', width=hb.w, speed=2)
        items += more
    return items, [T.Mark('heading', hbox)], sbox.bottom


def grid_room(L, top):
    """The room the tiles share: the safe area's width, from under the
    page's heading down to just above the link."""
    sa = L['safe']
    y = top + 24 * L['u']
    return Box(sa.x, y, sa.w, L['link'].y - 16 * L['u'] - y)


def cells(L, fmt, top):
    """Each tile's box on a page, in reading order: the same grid on every
    page, so a page of fewer tiles leaves its last cells empty."""
    cols, rows = GRIDS[fmt]
    room = grid_room(L, top)
    gap = TILE_GAP * L['u']
    w = (room.w - gap * (cols - 1)) / cols
    h = (room.h - gap * (rows - 1)) / rows
    return [Box(room.x + c * (w + gap), room.y + r * (h + gap), w, h)
            for r in range(rows) for c in range(cols)]


def tile_fonts(L):
    u = L['u']
    return dict(prop=T.font(26 * u, 700), num=T.font(46 * u, 700), title=T.font(30 * u, family=T.PRINT),
                url=T.font(26 * u, family=T.PRINT))


def clip_lines(lines, fnt, width, most):
    """`lines`, at most `most` of them, the last cut at a word with an
    ellipsis when there were more."""
    if len(lines) <= most:
        return list(lines)
    words = ' '.join(lines[most - 1:]).split()
    last = ''
    for w in words:
        if text.measure(f'{last} {w}…'.strip(), fnt) > width:
            break
        last = f'{last} {w}'.strip()
    return list(lines[:most - 1]) + [last.rstrip(',;:.') + '…']


def tile_parts(m, box, L):
    """A tile's contents laid out in `box`: (badge box or None, its fonts,
    title lines and their x, y, the one-liner's top, the url's y)."""
    u = L['u']
    F = tile_fonts(L)
    pad = TILE_PAD * u
    x, y = box.x + pad, box.y + pad
    inner = box.w - 2 * pad
    b = tile_badge(m)
    if b is None:
        bbox, tx = None, x
        bh = 0
    else:
        word, num = b
        bw = max(text.measure(word, F['prop']), text.measure(num, F['num'])) + 16 * u
        bh = text.line_height(F['prop']) * 0.85 + text.line_height(F['num']) * 0.8 + 6 * u
        bbox = Box(x, y, bw, bh)
        tx = x + bw + 14 * u
    tw = x + inner - tx
    title = clip_lines(text.wrap(short_title(m), F['title'], tw), F['title'], tw, TITLE_LINES)
    th = len(title) * text.line_height(F['title'])
    ty = y + max(0, (bh - th) / 2)
    line_top = y + max(bh, th) + 14 * u
    url_y = box.bottom - pad - text.line_height(F['url'])
    return dict(badge=bbox, word=b, F=F, title=title, tx=tx, ty=ty, tw=tw, line_top=line_top,
                url_y=url_y, inner=inner, x=x)


def line_font(L, fmt):
    """The one-liners' type: the largest, up to LINE_MAX, at which every
    member's one-liner fits its tile. One size for every tile in the
    course, so none is set larger than another."""
    box = cells(L, fmt, page_head(L, 1, len(COURSE.pages), 0)[2])[0]
    size = LINE_MAX * L['u']
    while True:
        fnt = T.font(size, 600)
        lh = text.line_height(fnt)
        fits = True
        for m in COURSE.members:
            p = tile_parts(m, box, L)
            room = p['url_y'] - 10 * L['u'] - p['line_top']
            if len(text.wrap(m.line.text, fnt, p['inner'])) * lh > room:
                fits = False
                break
        if fits or size < 18:
            return fnt
        size *= 0.97


def tile_items(m, box, L, fnt, s0, s1):
    """One tile drawn on over its slot's frames [s0, s1): its outline, the
    badge and title, then the one-liner written out at the pace it is
    said, then where its video is. Returns (items, marks)."""
    u = L['u']
    p = tile_parts(m, box, L)
    F = p['F']
    items = [stroke_item(s0, s0 + 8, Stroke(T.box_pts(*box), T.seed_of('tile'), passes=2, width=2.6 * u,
                                            closed=True, overshoot=0), GRAPHITE, alpha=0.6)]
    f = s0 + 2
    head = []
    if p['badge'] is not None:
        b = p['badge']
        word, num = p['word']
        head.append(stroke_item(f, f + 6, Stroke(T.box_pts(*b), T.seed_of('tile badge'), passes=2, width=2.4 * u,
                                                 closed=True, overshoot=0)))
        more, f, _ = T.write_lines(f + 6, [word], F['prop'], b.x, b.y + 0.15 * F['prop'].size, align='center',
                                   width=b.w, speed=3)
        head += more
        more, f, _ = T.write_lines(f, [num], F['num'], b.x, b.y + text.line_height(F['prop']) * 0.8,
                                   align='center', width=b.w, speed=3)
        head += more
    more, f, _ = T.write_lines(f, p['title'], F['title'], p['tx'], p['ty'], speed=3)
    head += more
    items += T.scaled(head, s0 + 2, TILE_WRITE + 4)
    # the one-liner, line by line, spread over the time it is said
    lines = text.wrap(m.line.text, fnt, p['inner'])
    lh = text.line_height(fnt)
    a = s0 + TILE_WRITE + 4
    said = max(a + len(lines), s0 + m.audio_frames - 4)
    widths = [text.measure(ln, fnt) for ln in lines]
    total = sum(widths)
    f = a
    for i, (ln, w) in enumerate(zip(lines, widths)):
        d = max(1, (said - a) * w / total)
        items.append(text_item(f, f + d, ln, fnt, p['x'], p['line_top'] + i * lh))
        f += d
    url = tile_url(m)
    more, f, ubox = T.write_lines(f + 1, [url], F['url'], p['x'], p['url_y'], align='center', width=p['inner'],
                                  alpha=URL_ALPHA, speed=4)
    items += T.scaled(more, more[0].f0, max(1, s1 - 2 - more[0].f0))
    done = int(max(it.f1 for it in items)) + 1
    return items, [T.Mark('tile', box, done), T.Mark('tile url', ubox, done)]


def tile_page(L, fmt, k, fnt):
    """Page k: its heading, written on in its lead, and its tiles, each
    drawn on in its own slot."""
    f0 = COURSE.page_start(k)
    items, marks, top = page_head(L, k + 1, len(COURSE.pages), f0 + T.FADE)
    items = T.scaled(items, f0 + T.FADE, max(1, COURSE.lead - T.FADE - 2))
    for i, box in zip(COURSE.pages[k], cells(L, fmt, top)):
        s0 = COURSE.slot_start(i)
        more, ms = tile_items(COURSE.members[i], box, L, fnt, s0, s0 + COURSE.slots[i])
        items += more
        marks += ms
    return items, marks


# ---- the closing page: still, and silent ----
CLOSING_WORDS = 'Every measure has its own one-minute video'


def closing_page(L):
    """Where each measure's own video is: CLOSING_WORDS over the state's
    page, underlined, centred on the stage."""
    st = L['stage']
    u = L['u']
    big = L['heading_font']
    mid = T.font(72 * u, family=T.PRINT)
    lines = text.wrap(CLOSING_WORDS, big, st.w * 0.9, balance=True)
    lh_big, lh_mid = text.line_height(big), text.line_height(mid)
    gap = 48 * u
    total = lh_big * len(lines) + gap + lh_mid
    y = st.y + (st.h - total) / 2
    f0 = COURSE.slots_end + T.FADE
    items, f, wbox = T.write_lines(f0, lines, big, st.x, y, align='center', width=st.w)
    y = wbox.bottom + gap
    more, f, lbox = T.write_lines(f + 2, [LINK], mid, st.x, y, align='center', width=st.w)
    items += more
    w = text.measure(LINK, mid)
    under = Stroke([(st.cx - w / 2 - 6, lbox.bottom + 2), (st.cx + w / 2 + 8, lbox.bottom + 4)],
                   T.seed_of('underline', LINK), passes=2, width=5 * u)
    items.append(stroke_item(f + 1, f + 9, under, ORANGE))
    # all of it on within its first second and a half: the rest is still
    items = T.scaled(items, f0, to_frame(1.5, FPS) - T.FADE)
    return items, [T.Mark('closing', wbox), T.Mark('closing link', lbox)]


# ---- the closing sources card: grouped by measure, over pages ----
SOURCES_PAGE = to_frame(SOURCES_CARD_SECONDS, FPS)  # each page's frames
GROUP_GAP = 0.9   # between two measures' groups, at least, in line heights
TITLE_GAP = 0.25  # under a measure's title, in line heights
PACK_SCALE = 0.8  # the type size, of the sources card's largest, pages are packed at
COLUMN_GAP = 80   # px between a 16x9 page's two columns, before L['u']


def title_font(sf):
    return T.font(sf.size, 700)


def group_lines(member, sf, width):
    """(title lines, number column width, each source's lines) for one
    measure's group at source font `sf`."""
    title = text.wrap(member.entry.title, title_font(sf), width, balance=True)
    num_w = text.measure(f'{len(member.cited)}.', sf) + 0.4 * sf.size
    blocks = [text.wrap(s.publisher, sf, width - num_w, balance=True) for s in member.cited]
    return title, num_w, blocks


def group_height(member, sf, width):
    title, _, blocks = group_lines(member, sf, width)
    lh = text.line_height(sf)
    return (len(title) * text.line_height(title_font(sf)) + TITLE_GAP * lh
            + sum(len(b) for b in blocks) * lh + T.SOURCES_GAP * lh * (len(blocks) - 1))


def room(L):
    _, _, hbox = heading_items(L, 'Sources', 0, L['heading'].y + 6)
    return T.sources_room(L, hbox)


def pack_pages():
    """The members' groups, in ballot order, packed onto pages: as many to a
    page as fit at PACK_SCALE of the card's largest type, in 9x16. The
    16x9 card has the same pages, so both formats are the same length and
    each page comes on at the same moment (sources_page lays a landscape
    page out in two columns)."""
    L = T.LAYOUTS['9x16']
    box = room(L)
    sf = T.font(L['sources_font'].size * PACK_SCALE, family=T.PRINT)
    gap = GROUP_GAP * text.line_height(sf)
    pages_, page, used = [], [], 0.0
    for m in COURSE.members:
        h = group_height(m, sf, box.w)
        if page and used + gap + h > box.h:
            pages_.append(page)
            page, used = [], 0.0
        used += (gap if page else 0) + h
        page.append(m)
    pages_.append(page)
    return pages_


def columns(L, members, box):
    """A page's groups split into columns, each [(x, width, members)]: one
    column the stage's width in 9x16; in 16x9, a page of two or more groups
    goes in two side by side, split in ballot order where the taller of
    the two is least."""
    if L['W'] < L['H'] or len(members) < 2:
        return [(box.x, box.w, members)]
    gap = COLUMN_GAP * L['u']
    w = (box.w - gap) / 2
    sf = L['sources_font']
    g = GROUP_GAP * text.line_height(sf)

    def height(ms):
        return sum(group_height(m, sf, w) for m in ms) + g * (len(ms) - 1)

    k = min(range(1, len(members)),
            key=lambda k: max(height(members[:k]), height(members[k:])))
    return [(box.x, w, members[:k]), (box.x + w + gap, w, members[k:])]


def sources_page(L, members, f0, k, of):
    """One page of the sources card: 'Sources' as its heading (with "k of
    n" under it when there are several), and each measure's title over
    its sources, numbered, at the largest type up to the card's that fits,
    the room left shared out between the groups (columns)."""
    hb = L['heading']
    items, f, hbox = heading_items(L, 'Sources', f0, hb.y + 6)
    marks = [T.Mark('heading', hbox)]
    box = T.sources_room(L, hbox)
    if of > 1:
        nf = T.font(36, family=T.PRINT)
        more, _, _ = T.write_lines(f, [f'{k} of {of}'], nf, box.x, box.y - text.line_height(nf) - 6,
                                   align='right', width=box.w, speed=2)
        items += more
    cols = columns(L, members, box)
    sf = L['sources_font']
    while True:
        lh = text.line_height(sf)
        gap = GROUP_GAP * lh
        heights = [sum(group_height(m, sf, w) for m in ms) + gap * (len(ms) - 1) for _, w, ms in cols]
        total = max(heights)
        if total <= box.h or sf.size < 22:
            break
        sf = T.font(sf.size * 0.97, family=T.PRINT)
    # the tallest column's spare room, shared out between its groups; the
    # other column (16x9) starts level with it, spaced alike
    tallest = cols[heights.index(total)][2]
    share = max(0, box.h - total) / (len(tallest) + 1)
    top = box.y + share
    bottom = top
    tf = title_font(sf)
    for x, w, ms in cols:
        y = top
        for m in ms:
            title, num_w, blocks = group_lines(m, sf, w)
            more, f, tbox = T.write_lines(f, title, tf, x, y, speed=2.2)
            items += more
            y = tbox.bottom + TITLE_GAP * lh
            for i, lines in enumerate(blocks):
                ni, _, _ = T.write_lines(f, [f'{i + 1}.'], sf, x, y, speed=2)
                items += ni
                li, f, _ = T.write_lines(f + 2, lines, sf, x + num_w, y, speed=2.2)
                items += li
                y += len(lines) * lh + T.SOURCES_GAP * lh
                f += 3
            y += gap + share - T.SOURCES_GAP * lh
        bottom = max(bottom, y)
    # every page's writing done well inside its time on screen
    items = T.scaled(items, f0, SOURCES_PAGE * 0.6)
    marks.append(T.Mark('sources', Box(box.x, top, box.w, max(1, bottom - share - gap - top))))
    return items, marks


PAGES = pack_pages()
FRAMES = COURSE.sources_start + SOURCES_PAGE * len(PAGES)


def build(L, fmt):
    """The film's groups in L's format: the opening card, each page of
    tiles, the closing page and the sources pages, each fading out as the
    next comes on."""
    groups = [T.Group(opening_card(L), [], 0, COURSE.opening - T.FADE)]
    fnt = line_font(L, fmt)
    for k in range(len(COURSE.pages)):
        items, marks = tile_page(L, fmt, k, fnt)
        # up to the next page's first frame, and fading out over its first
        # FADE: the page's last tile keeps its whole gap
        groups.append(T.Group(items, marks, COURSE.page_start(k), COURSE.page_start(k + 1)))
    items, marks = closing_page(L)
    groups.append(T.Group(items, marks, COURSE.slots_end, COURSE.sources_start - T.FADE))
    for k, members in enumerate(PAGES):
        f0 = COURSE.sources_start + k * SOURCES_PAGE
        items, marks = sources_page(L, members, f0 + 8, k + 1, len(PAGES))
        last = k + 1 == len(PAGES)
        groups.append(T.Group(items, marks, f0, None if last else f0 + SOURCES_PAGE - T.FADE))
    schedule = sorted((it for g in groups for it in g.items if it._head), key=lambda it: it.f0)
    return dict(L=L, groups=groups, schedule=schedule, line_font=fnt)


VIEWS = {fmt: build(T.LAYOUTS[fmt], fmt) for fmt in FORMATS}
OWN = VIEWS['9x16']  # whose lettering the drawing sound follows (sounds)


def draw(n, cv):
    """Frame n: the notebook page, the link and the footer, and whatever is
    on it."""
    own = VIEWS[cv.format.name]
    ctx = cv.ctx
    L = own['L']
    ctx.set_source_surface(sp.backdrop(cv.width, cv.height), 0, 0)
    ctx.paint()
    T.draw_footer(cv, L, L['footer'])
    T.draw_link(cv, L, L['link'])
    for g in own['groups']:
        g.draw(cv, n)
    T.draw_pencil(cv, n, own)


SEGMENTS = [vb.Segment('opening', 0, COURSE.opening,
                       data={'copy': [COURSE.state_name, COURSE.headline, COURSE.date]})]
for _k, _page in enumerate(COURSE.pages):
    SEGMENTS.append(vb.Segment(f'page {_k + 1}', COURSE.page_start(_k), COURSE.slot_start(_page[0]),
                               data={'copy': [COURSE.state_name, 'statewide measures']}))
    for _i in _page:
        _m = COURSE.members[_i]
        SEGMENTS.append(vb.Segment(_m.entry.id, COURSE.slot_start(_i), COURSE.slot_start(_i) + COURSE.slots[_i],
                                   data={'copy': [short_title(_m), _m.line.text, tile_url(_m)]}))
SEGMENTS.append(vb.Segment('closing', COURSE.slots_end, COURSE.sources_start,
                           data={'copy': [CLOSING_WORDS, LINK]}))
SEGMENTS.append(vb.Segment('sources', COURSE.sources_start, FRAMES,
                           data={'copy': ['Sources'] + [s.publisher for m in COURSE.members for s in m.cited]}))
TIMELINE = vb.Timeline(GRID, SEGMENTS, end=FRAMES)
# one chapter per measure, which `render` writes next to the video
CHAPTERS = cc.chapters(COURSE)


def sounds():
    """Each tile's cut of its measure's committed narration, at its slot's
    start; and the drawing sound, levelled under the first member's
    narration."""
    out = []
    for i, m in enumerate(COURSE.members):
        out.append(vb.Sound(path=str(Path(m.contest.path, 'narration.wav')), at=COURSE.slot_start(i),
                            start=m.audio_from, frames=m.audio_frames, fade_in_frames=cc.AUDIO_FADE,
                            fade_out_frames=cc.AUDIO_FADE))
    out.append(dsnd.sound_for(OWN['schedule'], FPS, FRAMES,
                              voice_rms=dsnd.narration_rms(T.VOICE.path)))
    return tuple(out)


SOUNDS = sounds()
# frames worth a look: the opening card, each page of tiles whole, the
# closing page, and each sources page
KEYFRAMES = ((COURSE.opening - 1, 'opening'),
             *((COURSE.page_start(k + 1) - 1, f'page {k + 1}') for k in range(len(COURSE.pages))),
             (COURSE.sources_start - T.FADE - 1, 'closing'),
             *((COURSE.sources_start + (k + 1) * SOURCES_PAGE - 1, f'sources {k + 1}') for k in range(len(PAGES))))

FILM = vb.Film(
    draw=draw,
    timeline=TIMELINE,
    formats=FORMATS,
    background='#f2ebd8',
    sounds=SOUNDS,
    keyframes=tuple(sorted(KEYFRAMES)),
)

if __name__ == '__main__':
    vb.main(__file__)
