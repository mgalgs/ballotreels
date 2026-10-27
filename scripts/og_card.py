"""Draws the site-wide link-preview card (ballotreels/site/static/
og-card.png, 1200x630): the site's graph paper, brand mark and fonts.
Run it again only to change the card:

    python scripts/og_card.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STATIC = Path(__file__).resolve().parent.parent / "ballotreels" / "site" / "static"
OUT = STATIC / "og-card.png"
W, H = 1200, 630

# style.css's --paper, --ink, --ink-soft, --accent and grid line.
PAPER = (243, 238, 223)
INK = (46, 43, 39)
INK_SOFT = (95, 88, 78)
ACCENT = (224, 123, 51)
GRID = (226, 219, 200)


def font(name, size, weight=None):
    f = ImageFont.truetype(str(STATIC / "fonts" / name), size)
    if weight is not None:
        f.set_variation_by_axes([weight])
    return f


def main():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 30):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 30):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    # The header's brand mark, scaled up: a phone with a play triangle.
    s = 6.2
    ox, oy = 110, 175
    d.rounded_rectangle([ox + 6 * s, oy + 2.5 * s, ox + 20 * s, oy + 23.5 * s],
                        radius=2.5 * s, outline=INK, width=12)
    d.polygon([(ox + 11 * s, oy + 9.5 * s), (ox + 16.5 * s, oy + 13 * s),
               (ox + 11 * s, oy + 16.5 * s)], fill=ACCENT)

    left = 330
    d.text((left, 120), "ballotreels", font=font("Caveat-Variable.ttf", 150, 700),
           fill=INK)
    tagline = "Your ballot, explained"
    tag_font = font("Caveat-Variable.ttf", 92, 600)
    d.text((left, 290), tagline, font=tag_font, fill=INK)
    # The orange pencil line under the words, as under every heading.
    tw = d.textlength(tagline, font=tag_font)
    d.line([(left, 398), (left + tw * 0.5, 392), (left + tw, 400)],
           fill=ACCENT, width=9, joint="curve")

    body = font("PatrickHand-Regular.ttf", 44)
    d.text((left, 445), "Short, even-handed videos.", font=body, fill=INK_SOFT)
    d.text((left, 500), "Every claim sourced.", font=body, fill=INK_SOFT)
    img.save(OUT, optimize=True)


if __name__ == "__main__":
    main()
