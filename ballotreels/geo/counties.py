"""counties.json: which counties each city and school district lies in,
for the county pages (/<st>/<year>/county/<county>), worked out from the
shapes `geo build` writes (<data-dir>/geo/<state>/county.geojson,
place.geojson, school_district.geojson), so it needs no download. `geo
build` writes it last; `geo counties` writes it again from a build
already on disk.

A district is in a county where the two share ground, not merely a
border: the shapes are simplified independently (build.py's
`tolerance`), so where a district's edge is the county line the two
outlines can cross each other by a sliver as wide as about twice that
tolerance. Each county's share of a district is measured along
horizontal and along vertical lines (ballotreels.geo.shapes.
row_intervals), and each piece of it on a line is trimmed by MARGIN at
both ends; the county counts only where a kept piece of a row crosses a
kept piece of a column. A sliver, narrow one way or the other (or an L
of slivers, one each way), leaves no such crossing, while ground any
wider than 2 * MARGIN both ways does. A district too small
to leave anything anywhere is in the county holding most of it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .lookup import ballot_division
from .outline import mini_outline
from .shapes import point_in_polygon, row_intervals, simplify_ring

FILENAME = "counties.json"

# The local kinds placed in counties, each with its shapes file.
LOCAL_KINDS = ("place", "school_district")

# The spacing, in degrees, of the lines the shapes are measured along
# (about 110 m north-south).
STEP = 0.001
# What each piece of a county's share of a district loses at each end
# before it counts (about 150 m): more than the 0.001-degree tolerance
# of `geo build`'s outlines, on each side of a shared line, so a sliver
# where both outlines mean the county line never counts.
MARGIN = 0.0015

# The county outlines kept for the pages' map (the hero): projected to
# a box whose longer side is HERO_SIZE units and simplified to within
# HERO_TOLERANCE of them, which keeps a state's few dozen counties to
# tens of KB of SVG path.
HERO_SIZE = 1000
HERO_TOLERANCE = 1.2


class CountiesError(Exception):
    """A geo build that cannot be read for its counties."""


def _features(geo_dir: Path, kind: str, required: bool) -> list[dict]:
    path = geo_dir / f"{kind}.geojson"
    if not path.is_file() and not required:
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CountiesError(f"{path}: cannot read ({e}); run `python -m "
                            f"ballotreels geo build` first") from None
    out = []
    for feature in doc.get("features", ()):
        props = feature.get("properties") or {}
        rings = [[(float(x), float(y)) for x, y in ring]
                 for ring in (feature.get("geometry") or {}).get(
                     "coordinates", ())]
        if not props.get("ocd_id") or not rings:
            raise CountiesError(f"{path}: a feature has no ocd_id or shape")
        out.append({"ocd_id": props["ocd_id"],
                    "name": props.get("name") or props["ocd_id"],
                    "rings": rings})
    return out


def _swap(rings):
    return [[(y, x) for x, y in ring] for ring in rings]


def _bbox(rings) -> tuple[float, float, float, float]:
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


class _Shape:
    """A shape as row intervals along both axes."""

    def __init__(self, rings):
        self.rings = rings
        self.box = _bbox(rings)
        self.rows = row_intervals(rings, STEP)
        self.cols = row_intervals(_swap(rings), STEP)


def _pieces(a, b) -> list[tuple[float, float]]:
    """Where two sorted lists of disjoint intervals overlap, touching
    pieces joined."""
    out: list[tuple[float, float]] = []
    i = j = 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            if out and lo <= out[-1][1]:
                out[-1] = (out[-1][0], hi)
            else:
                out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def _kept(mine: dict, theirs: dict) -> tuple[float, dict]:
    """(the length the two shapes share over all lines, line k -> the
    pieces of it left with each trimmed by MARGIN at both ends)."""
    raw = 0.0
    kept: dict[int, list[tuple[float, float]]] = {}
    for k, ivs in mine.items():
        other = theirs.get(k)
        if not other:
            continue
        for lo, hi in _pieces(ivs, other):
            raw += hi - lo
            if hi - lo > 2 * MARGIN:
                kept.setdefault(k, []).append((lo + MARGIN, hi - MARGIN))
    return raw, kept


def _crossing(across: dict, down: dict) -> bool:
    """Whether a kept piece of a row and a kept piece of a column cross:
    a point of the shared ground at least MARGIN from its edge both east-
    west and north-south. A sliver one way on one stretch and the other
    way on another leaves pieces of both that never meet."""
    for col, ivs in down.items():
        x = (col + 0.5) * STEP
        for lo, hi in ivs:
            for row in range(math.ceil(lo / STEP - 0.5),
                             math.floor(hi / STEP - 0.5) + 1):
                if any(a <= x <= b for a, b in across.get(row, ())):
                    return True
    return False


def _overlaps(box, other) -> bool:
    return not (box[2] <= other[0] or other[2] <= box[0] or
                box[3] <= other[1] or other[3] <= box[1])


def district_counties(district: _Shape,
                      counties: dict[str, _Shape]) -> list[str]:
    """The counties `district` shares ground with (see the module's
    docstring), in `counties`' order; never none if it lies in any."""
    found = []
    best, best_raw = None, 0.0
    for county_id, county in counties.items():
        if not _overlaps(district.box, county.box):
            continue
        raw, across = _kept(district.rows, county.rows)
        if raw > best_raw:
            best, best_raw = county_id, raw
        if not across:
            continue
        _, down = _kept(district.cols, county.cols)
        if _crossing(across, down):
            found.append(county_id)
    if found:
        return found
    if best is not None:
        return [best]
    # A district no line crosses: the county its middle is in.
    x0, y0, x1, y1 = district.box
    middle = ((x0 + x1) / 2, (y0 + y1) / 2)
    return [county_id for county_id, county in counties.items()
            if point_in_polygon(middle, county.rings)][:1]


def _hero(counties: list[dict]) -> dict[str, Any]:
    """Every county's outline as an SVG path in one shared box,
    longitude scaled by the cosine of the state's middle latitude (so
    the shape is not stretched), north up."""
    boxes = [_bbox(c["rings"]) for c in counties]
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    squash = math.cos(math.radians((y0 + y1) / 2))
    width, height = (x1 - x0) * squash, y1 - y0
    scale = HERO_SIZE / max(width, height, 1e-9)
    w, h = round(width * scale), round(height * scale)
    paths = {}
    for county in counties:
        parts = []
        for ring in county["rings"]:
            projected = [((x - x0) * squash * scale, (y1 - y) * scale)
                         for x, y in ring]
            simple = simplify_ring(projected, HERO_TOLERANCE)
            if simple is None:
                continue
            pts = [(round(x), round(y)) for x, y in simple[:-1]]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            if len(pts) < 3:
                continue
            d = [f"M{pts[0][0]} {pts[0][1]}l"]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                d.append(f"{bx - ax} {by - ay} ")
            parts.append("".join(d).rstrip() + "z")
        if parts:
            paths[county["ocd_id"]] = "".join(parts).replace(" -", "-")
    return {"width": max(w, 1), "height": max(h, 1), "paths": paths}


def county_doc(geo_dir: str | Path) -> dict[str, Any]:
    """counties.json's content: `{"counties": {county ocd-id: {"name",
    "divisions": [the city and school-district ocd-ids in it, sorted]}},
    "hero": {"width", "height", "paths": {county ocd-id: SVG path}},
    "mini": {"width", "height", "path"}}`, `mini` the state's outer
    outline for the home page's icon (ballotreels.geo.outline).
    A school district's 9-12-only territory counts as the district
    (ballotreels.geo.lookup.ballot_division)."""
    geo_dir = Path(geo_dir)
    counties = _features(geo_dir, "county", required=True)
    shapes = {c["ocd_id"]: _Shape(c["rings"]) for c in counties}
    members: dict[str, set[str]] = {c["ocd_id"]: set() for c in counties}
    for kind in LOCAL_KINDS:
        for district in _features(geo_dir, kind, required=False):
            division = ballot_division(district["ocd_id"])
            for county_id in district_counties(_Shape(district["rings"]),
                                               shapes):
                members[county_id].add(division)
    return {
        "counties": {c["ocd_id"]: {"name": c["name"],
                                   "divisions": sorted(members[c["ocd_id"]])}
                     for c in sorted(counties, key=lambda c: c["name"])},
        "hero": _hero(counties) if counties else None,
        "mini": mini_outline([c["rings"] for c in counties]),
    }


def write_counties(geo_dir: str | Path) -> Path:
    """Writes `<geo_dir>/counties.json`; returns its path."""
    doc = county_doc(geo_dir)
    out = Path(geo_dir) / FILENAME
    part = out.with_name(out.name + ".part")
    part.write_text(json.dumps(doc, ensure_ascii=False,
                               separators=(",", ":")), encoding="utf-8")
    part.replace(out)
    return out
