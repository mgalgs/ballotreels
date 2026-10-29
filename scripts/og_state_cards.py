"""Draws each state's link-preview card (ballotreels/site/static/og/
<st>.jpg, 1200x630): the state's flag inside its outline, from the state
page's hero (var/geo/<st>/counties.json), beside its name. In a state
with local measures each county gets one too (og/<st>/<county slug>.jpg,
pages.county_card_path), its county hatched in orange. Run it after
`geo counties` or a new flag:

    python scripts/og_state_cards.py [st...]
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path[:0] = [str(Path(__file__).resolve().parent.parent),
                str(Path(__file__).resolve().parent)]
from ballotreels.geo.states import STATE_NAMES  # noqa: E402
from ballotreels.index import load_index  # noqa: E402
from ballotreels.site.pages import (county_card_path,  # noqa: E402
                                    election_date, state_card_path)
from og_card import (ACCENT, GRID, H, INK, INK_SOFT, PAPER,  # noqa: E402
                     STATIC, W, font)

REPO = Path(__file__).resolve().parent.parent
OUT = STATIC / "og"
# The box the state is drawn in, left of the words.
BOX = (50, 55, 560, 575)
LEFT, RIGHT = 610, 1160


def rings(d: str) -> list[list[tuple[float, float]]]:
    """An SVG path of only M, l and z (pages.hero_svg's) as point lists."""
    out = []
    for part in re.findall(r"M[^M]*", d):
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", part)]
        x, y = nums[0], nums[1]
        ring = [(x, y)]
        for dx, dy in zip(nums[2::2], nums[3::2]):
            x, y = x + dx, y + dy
            ring.append((x, y))
        out.append(ring)
    return out


def fitted(text: str, name: str, size: int, weight, width: float):
    """The font at `size` or smaller so `text` fits in `width`."""
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while size > 20:
        f = font(name, size, weight)
        if probe.textlength(text, font=f) <= width:
            return f
        size -= 4
    return font(name, size, weight)


def _mask(shapes) -> Image.Image:
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for ring in shapes:
        if len(ring) > 2:
            md.polygon(ring, fill=255, outline=255, width=2)
    return mask


def card(abbr: str, name: str, hero: dict, county: str | None = None,
         lines_below: tuple[str, str] = ("Short, even-handed videos.",
                                         "Every claim sourced.")
         ) -> Image.Image:
    hw, hh = int(hero["width"]), int(hero["height"])
    bx0, by0, bx1, by1 = BOX
    scale = min((bx1 - bx0) / hw, (by1 - by0) / hh)
    ox = bx0 + ((bx1 - bx0) - hw * scale) / 2
    oy = by0 + ((by1 - by0) - hh * scale) / 2
    place = lambda d: [[(ox + x * scale, oy + y * scale) for x, y in ring]
                       for ring in rings(d)]
    shapes = [ring for d in hero["paths"].values() for ring in place(d)]

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 30):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 30):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    land = _mask(shapes)
    # The pencil edge: the land grown a few pixels, less the land.
    edge = ImageChops.subtract(land.filter(ImageFilter.MaxFilter(9)), land)
    img.paste(INK, mask=edge)

    # The flag covers the hero's box, as the state page's does
    # (preserveAspectRatio slice).
    flag = Image.open(STATIC / "flags" / f"{abbr}.jpg").convert("RGB")
    fw, fh = round(hw * scale), round(hh * scale)
    k = max(fw / flag.width, fh / flag.height)
    flag = flag.resize((max(1, round(flag.width * k)),
                        max(1, round(flag.height * k))), Image.LANCZOS)
    cx, cy = (flag.width - fw) // 2, (flag.height - fh) // 2
    flag = flag.crop((cx, cy, cx + fw, cy + fh))
    layer = Image.new("RGB", (W, H), PAPER)
    layer.paste(flag, (round(ox), round(oy)))
    img.paste(layer, mask=land)

    if county is not None:
        # As the county page's hero: the county hatched and edged in
        # orange; the rest of the state washed back so it stands out.
        mine = _mask(place(hero["paths"][county]))
        rest = ImageChops.subtract(land, mine)
        img.paste(Image.blend(img, Image.new("RGB", (W, H), PAPER), 0.55),
                  mask=rest)
        hatch = Image.new("L", (W, H), 0)
        hd = ImageDraw.Draw(hatch)
        for x in range(-H, W, 11):
            hd.line([(x, H), (x + H, 0)], fill=220, width=3)
        img.paste(ACCENT, mask=ImageChops.multiply(hatch, mine))
        ring = ImageChops.subtract(mine.filter(ImageFilter.MaxFilter(9)),
                                   mine)
        img.paste(ACCENT, mask=ring)

    d = ImageDraw.Draw(img)
    width = RIGHT - LEFT
    d.text((LEFT, 60), "ballotreels", font=font("Caveat-Variable.ttf", 64, 700),
           fill=INK_SOFT)
    lines = name.split(" ") if len(name) > 14 and " " in name else [name]
    if len(lines) > 2:
        half = (len(lines) + 1) // 2
        lines = [" ".join(lines[:half]), " ".join(lines[half:])]
    big = min((fitted(ln, "Caveat-Variable.ttf", 120, 700, width)
               for ln in lines), key=lambda f: f.size)
    y = 150 if len(lines) == 1 else 120
    for ln in lines:
        d.text((LEFT, y), ln, font=big, fill=INK)
        y += round(big.size * 0.95)
    tagline = "ballot measures, explained"
    tag = fitted(tagline, "Caveat-Variable.ttf", 72, 600, width)
    y += 10
    d.text((LEFT, y), tagline, font=tag, fill=INK)
    tw = d.textlength(tagline, font=tag)
    uy = y + round(tag.size * 1.05)
    d.line([(LEFT, uy + 4), (LEFT + tw * 0.5, uy - 2), (LEFT + tw, uy + 6)],
           fill=ACCENT, width=8, joint="curve")
    first, second = lines_below
    d.text((LEFT, uy + 40), first,
           font=fitted(first, "PatrickHand-Regular.ttf", 40, None, width),
           fill=INK_SOFT)
    d.text((LEFT, uy + 90), second,
           font=fitted(second, "PatrickHand-Regular.ttf", 40, None, width),
           fill=INK_SOFT)
    return img


def has_local_measures(abbr: str) -> tuple[bool, str | None]:
    """Whether the state's election has any measure below statewide, and
    the election's id."""
    for election_dir in sorted((REPO / "data").glob(f"{abbr}-*")):
        index = load_index(election_dir)
        local = any(e.kind == "measure"
                    and e.division != index.election.state
                    for e in index.entries)
        return local, index.election.id
    return False, None


def main(argv: list[str]) -> int:
    OUT.mkdir(exist_ok=True)
    wanted = argv or sorted(p.name for p in (REPO / "var" / "geo").iterdir()
                            if (p / "counties.json").is_file())
    for abbr in wanted:
        if not (STATIC / "flags" / f"{abbr}.jpg").is_file():
            print(f"{abbr}: no flag; skipped", file=sys.stderr)
            continue
        geo = json.loads((REPO / "var" / "geo" / abbr / "counties.json")
                         .read_text(encoding="utf-8"))
        name = STATE_NAMES[abbr].removeprefix("the ")
        path = STATIC / state_card_path(abbr)
        card(abbr, name, geo["hero"]).save(path, quality=86, optimize=True)
        print(f"{path}: written")
        local, election_id = has_local_measures(abbr)
        if not local:
            continue
        when = election_date(election_id) or ""
        below = (f"{name}, {when}" if when else name,
                 "Short, even-handed videos.")
        for county, info in geo["counties"].items():
            if county not in geo["hero"]["paths"]:
                continue
            path = STATIC / county_card_path(abbr, county)
            path.parent.mkdir(exist_ok=True)
            card(abbr, info["name"], geo["hero"], county, below).save(
                path, quality=86, optimize=True)
        print(f"{STATIC / 'og' / abbr}/: {len(geo['counties'])} counties")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
