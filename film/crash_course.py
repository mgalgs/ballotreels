"""The state crash course film, template version 2 (ballotreels.crash_course).

    python -m ballotreels render data/ut-2026-11-03 --format 9x16
    python -m ballotreels render data/ut-2026-11-03 --format 16x9
    BALLOTREELS_CRASH_COURSE=data/ut-2026-11-03 python film/crash_course.py sheet

One video through every statewide measure on a state's ballot, in
contests.toml's order, that says nothing of its own. It reads the
election named by BALLOTREELS_CRASH_COURSE (default: Utah's) and lays it
out with ballotreels.crash_course.plan:

- an opening card, on screen only, with no narration: the state's name,
  how many statewide measures it has, and the election's date;
- one slot per measure, as long as that measure's own sections: its own
  film (film/measure.py, loaded once per member, unchanged) replayed for
  its opening section and its vote section (a choice question's
  `choices` section), each with the stretch of the measure's committed
  narration under it, cut by its phrase timings; the slot then holds the
  vote section's last frame, silent and with no caption, for
  ballotreels.crash_course.SLOT_GAP_SECONDS, and is never padded out to
  match a longer one;
- a closing sources card, in the measure film's style: what the reused
  lines cite, grouped under each measure's title, over as many pages as
  it takes.

A replayed section is drawn as its own film draws it, with nothing left
over from the sections the slot skips: no page fading out from the one
before, no caption, pencil or countdown ring of another section (Part
below). On every frame, the link under the caption is the state's page
(ballotreels.org/<st>/<year>), where the crash course is shown, not a
measure's own.

Phone-first: 9:16 is the default format, and the only one the pipeline
renders. The 16:9 format, for YouTube, is rendered from the command line
only. It has the same frames, sound and chapters: each slot replays the
member film's own 16x9 plan, and the opening card and sources pages are
laid out for landscape, the sources pages being 9:16's pages (so each
comes on at the same moment), with two or more groups set in two columns.
The drawing sounds stay the 9x16 schedule's, as the measure film's do.
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
from sketch import ORANGE, Stroke, stroke_item  # noqa: E402

from ballotreels import crash_course as cc  # noqa: E402
from ballotreels.ballots import state_of  # noqa: E402
from ballotreels.site import pages  # noqa: E402
from ballotreels.site.config import DEFAULT_SITE_URL  # noqa: E402
from ballotreels.storyboard import SOURCES_CARD_SECONDS  # noqa: E402
from ballotreels.storyboard import frame as to_frame  # noqa: E402

MEASURE_FILM = HERE / 'measure.py'

# ---- the election, and its measures' own films ----
ELECTION_DIR = Path(os.environ.get(
    'BALLOTREELS_CRASH_COURSE', str(REPO_ROOT / 'data' / 'ut-2026-11-03')))
COURSE = cc.plan(ELECTION_DIR)
FPS = COURSE.fps
GRID = vb.Grid(fps=FPS, bpm=FPS * 60)  # one frame a beat, as the measure film

# the state's page on the site, where the crash course is shown, printed
# under the caption on every frame (in the measure films' own place)
SITE_URL = os.environ.get('BALLOTREELS_SITE_URL') or DEFAULT_SITE_URL
LINK = pages.display_url(SITE_URL, '/{}/{}'.format(
    state_of(COURSE.election.state) or COURSE.election.id[:2],
    pages.election_year(COURSE.election.id)))


def load_member(member):
    """film/measure.py for `member`, as its own render loads it, with the
    link it prints on every frame swapped for the state page's."""
    old = os.environ.get('BALLOTREELS_CONTEST')
    os.environ['BALLOTREELS_CONTEST'] = str(Path(member.contest.path).resolve())
    try:
        mod = vb.load_module(str(MEASURE_FILM))
    finally:
        if old is None:
            os.environ.pop('BALLOTREELS_CONTEST', None)
        else:
            os.environ['BALLOTREELS_CONTEST'] = old
    if [(s.label, s.start, s.end) for s in mod.BOARD.sections] != \
            [(s.label, s.start, s.end) for s in member.board.sections]:
        raise ValueError(f'{member.entry.id}: its film and the crash course lay it out differently')
    mod.LINK = LINK
    return mod


FILMS = tuple(load_member(m) for m in COURSE.members)
T = FILMS[0]  # the template's helpers and layout, the same in every member's film
# 9x16 first: the default, and the only one the pipeline renders; 16x9 is
# rendered from the command line (`render <election-dir> --format 16x9`)
FORMATS = ('9x16', '16x9')


class Part:
    """One replayed section of a member's film: its plan for `fmt` (the
    film's own, PLANS) cut down to what is on the page within frames
    [start, end) of that film, so nothing from the sections the slot skips
    shows. `hold`: the frame held after the part, with no caption, pencil
    or ring."""

    def __init__(self, mod, part, fmt, hold=False):
        P = mod.PLANS[fmt]
        a, b = part.start, part.end
        groups = [g for g in P['groups']
                  if g.f0 < b and (g.out is None or g.out > a)]
        kept = {id(it) for g in groups for it in g.items}
        self.mod = mod
        self.plan = dict(
            P, groups=groups,
            schedule=[] if hold else [it for it in P['schedule'] if id(it) in kept and a <= it.f0 < b],
            slides=[] if hold else [(s0, s1) for s0, s1 in P['slides'] if s1 > a and s0 < b],
            # the part's own words only: a caption of the section before or
            # after it would show words this slot does not say
            captions=[] if hold else [c for c in P['captions']
                                      if part.said_from - 0.1 - 1e-6 <= c['start'] < part.said_to])
        self.page_spans = [(s0, s1) for s0, s1 in mod.PAGE_SPANS if s1 >= a and s0 < b]
        self.own_spans = mod.PAGE_SPANS

    def draw(self, n, cv):
        # page_view (the full-page view's fade) reads the film's PAGE_SPANS
        self.mod.PAGE_SPANS = self.page_spans
        try:
            self.mod.draw(n, cv, self.plan)
        finally:
            self.mod.PAGE_SPANS = self.own_spans


def slots(fmt):
    """Each slot's (member film, its parts' views, and the view holding the
    last frame), in `fmt`."""
    return [(mod, [Part(mod, p, fmt) for p in m.parts], Part(mod, m.parts[-1], fmt, hold=True))
            for m, mod in zip(COURSE.members, FILMS)]


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
FRAMES = COURSE.slots_end + SOURCES_PAGE * len(PAGES)


def build(L):
    """The film's own groups in L's format: the opening card, and the
    sources pages, each page fading out as the next comes on."""
    groups = [T.Group(opening_card(L), [], 0, COURSE.opening - T.FADE)]
    for k, members in enumerate(PAGES):
        f0 = COURSE.slots_end + k * SOURCES_PAGE
        items, marks = sources_page(L, members, f0 + 8, k + 1, len(PAGES))
        last = k + 1 == len(PAGES)
        groups.append(T.Group(items, marks, f0, None if last else f0 + SOURCES_PAGE - T.FADE))
    schedule = sorted((it for g in groups for it in g.items if it._head), key=lambda it: it.f0)
    return dict(L=L, groups=groups, schedule=schedule)


# each format's own cards and slots
VIEWS = {fmt: dict(own=build(T.LAYOUTS[fmt]), slots=slots(fmt)) for fmt in FORMATS}
OWN = VIEWS['9x16']['own']  # whose lettering the cards' drawing sound follows (sounds)


def draw_own(n, cv, own):
    """A frame of the opening card or the sources card: the notebook page,
    the link and the footer, and the card's own lettering."""
    ctx = cv.ctx
    L = own['L']
    ctx.set_source_surface(sp.backdrop(cv.width, cv.height), 0, 0)
    ctx.paint()
    T.draw_footer(cv, L, L['footer'])
    T.draw_link(cv, L, L['link'])
    for g in own['groups']:
        g.draw(cv, n)
    T.draw_pencil(cv, n, own)


def at(n, fmt='9x16'):
    """What frame n shows in `fmt`: (view, frame of its film), or None for
    the film's own cards."""
    if n < COURSE.opening or n >= COURSE.slots_end:
        return None
    i = 0
    while n >= COURSE.slot_start(i + 1):
        i += 1
    k = n - COURSE.slot_start(i)
    mod, parts, hold = VIEWS[fmt]['slots'][i]
    for view, p in zip(parts, COURSE.members[i].parts):
        if k < p.frames:
            return view, p.start + k
        k -= p.frames
    return hold, COURSE.members[i].parts[-1].end - 1


def draw(n, cv):
    fmt = cv.format.name
    shown = at(n, fmt)
    if shown is None:
        draw_own(n, cv, VIEWS[fmt]['own'])
        return
    view, m = shown
    view.draw(m, cv)

SEGMENTS = [vb.Segment('opening', 0, COURSE.opening,
                       data={'copy': [COURSE.state_name, COURSE.headline, COURSE.date]})]
for _i, _m in enumerate(COURSE.members):
    SEGMENTS.append(vb.Segment(_m.entry.id, COURSE.slot_start(_i), COURSE.slot_start(_i + 1),
                               data={'copy': [_m.entry.title] + [ln.text for ln in _m.lines]}))
SEGMENTS.append(vb.Segment('sources', COURSE.slots_end, FRAMES,
                           data={'copy': ['Sources'] + [s.publisher for m in COURSE.members for s in m.cited]}))
TIMELINE = vb.Timeline(GRID, SEGMENTS, end=FRAMES)
# one chapter per measure, which `render` writes next to the video
CHAPTERS = cc.chapters(COURSE)


def sounds():
    """Each part's cut of its measure's committed narration, under the
    part's picture, and that picture's own drawing sound; the cards'
    lettering gets its own, levelled under the first member's narration."""
    out = []
    for i, (m, mod) in enumerate(zip(COURSE.members, FILMS)):
        pos = COURSE.slot_start(i)
        for p in m.parts:
            out.append(vb.Sound(path=str(mod.VOICE.path), at=pos + p.audio_at, start=p.audio_from,
                                frames=p.audio_frames, fade_in_frames=cc.AUDIO_FADE,
                                fade_out_frames=cc.AUDIO_FADE))
            out.append(vb.Sound(path=mod.DRAW_SOUND.path, at=pos, start=p.start / FPS, frames=p.frames,
                                fade_in_frames=2, fade_out_frames=2, ducks=False))
            pos += p.frames
    out.append(dsnd.sound_for(OWN['schedule'], FPS, FRAMES,
                              voice_rms=dsnd.narration_rms(T.VOICE.path)))
    return tuple(out)


SOUNDS = sounds()
# frames worth a look: the opening card, each slot's first and last
# frames, and each sources page
KEYFRAMES = ((COURSE.opening - 1, 'opening'),
             *((COURSE.slot_start(i), f'{m.entry.id} first') for i, m in enumerate(COURSE.members)),
             *((COURSE.slot_start(i + 1) - 1, f'{m.entry.id} last') for i, m in enumerate(COURSE.members)),
             *((COURSE.slots_end + (k + 1) * SOURCES_PAGE - 1, f'sources {k + 1}') for k in range(len(PAGES))))

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
