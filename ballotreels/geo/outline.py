"""A state's outer outline, coarse enough for an icon: the home page's
state buttons draw it (counties.json's `mini`, ballotreels.geo.counties).

The counties are not joined as polygons (their outlines are simplified
independently, so neighbours never quite share an edge): they are
painted onto a grid, the hairline gaps between neighbours closed, every
lake or hole inside filled, and the edge of each piece of land left
traced, simplified and kept if it is big enough to see at icon size.
"""

from __future__ import annotations

import math

from .shapes import row_intervals, simplify_ring

# The outline's box: its longer side MINI_SIZE units, integer
# coordinates. Each unit is painted as GRID x GRID cells.
MINI_SIZE = 100
GRID = 4
# The most SVG path one state's outline may take, and the tolerance its
# simplification starts at (in units), loosened until it fits.
MINI_BUDGET = 800
MINI_TOLERANCE = 0.8
# A piece of land smaller than this (in square units: about a 5 x 5
# square, under 2 px on a 36 px icon) is dropped, the largest never.
MIN_PART_AREA = 25.0

_PAD = 2


def _project(counties: list[list[list[tuple[float, float]]]]):
    """Each county's rings in grid cells, longitude scaled by the cosine
    of the middle latitude, north up (as counties._hero); and the box's
    width and height in units."""
    pts = [p for rings in counties for ring in rings for p in ring]
    x0 = min(x for x, _ in pts)
    x1 = max(x for x, _ in pts)
    y0 = min(y for _, y in pts)
    y1 = max(y for _, y in pts)
    squash = math.cos(math.radians((y0 + y1) / 2))
    width, height = (x1 - x0) * squash, y1 - y0
    scale = MINI_SIZE / max(width, height, 1e-12)
    cell = scale * GRID
    projected = [[[((x - x0) * squash * cell + _PAD, (y1 - y) * cell + _PAD)
                   for x, y in ring] for ring in rings]
                 for rings in counties]
    return projected, max(round(width * scale), 1), max(round(height * scale), 1)


def _paint(projected, cols: int, rows: int) -> list[bytearray]:
    """The grid: a cell is land if its middle is in any county."""
    land = [bytearray(cols) for _ in range(rows)]
    for rings in projected:
        for k, ivs in row_intervals(rings, 1.0).items():
            if not 0 <= k < rows:
                continue
            row = land[k]
            for lo, hi in ivs:
                for c in range(max(math.ceil(lo - 0.5), 0),
                               min(math.floor(hi - 0.5), cols - 1) + 1):
                    row[c] = 1
    return land


def _close(land: list[bytearray]) -> list[bytearray]:
    """Grown by a cell then shrunk by one: a gap a cell or two wide
    between neighbouring counties is filled, the outer edge kept."""
    rows, cols = len(land), len(land[0])

    def step(grid, value):
        out = [bytearray(row) for row in grid]
        for r in range(1, rows - 1):
            above, row, below, new = grid[r - 1], grid[r], grid[r + 1], out[r]
            for c in range(1, cols - 1):
                if row[c] != value and (above[c] == value or
                                        below[c] == value or
                                        row[c - 1] == value or
                                        row[c + 1] == value):
                    new[c] = value
        return out

    return step(step(land, 1), 0)


def _fill_holes(land: list[bytearray]) -> None:
    """Every cell the sea outside cannot reach becomes land."""
    rows, cols = len(land), len(land[0])
    sea = [bytearray(cols) for _ in range(rows)]
    todo = [(0, 0)]
    sea[0][0] = 1
    while todo:
        r, c = todo.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (0 <= nr < rows and 0 <= nc < cols and not sea[nr][nc]
                    and not land[nr][nc]):
                sea[nr][nc] = 1
                todo.append((nr, nc))
    for r in range(rows):
        for c in range(cols):
            if not sea[r][c]:
                land[r][c] = 1


def _trace(land: list[bytearray]) -> list[list[tuple[int, int]]]:
    """The edge of each piece of land, as rings of grid corners, land on
    the right of the way round (clockwise on screen)."""
    rows, cols = len(land), len(land[0])
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if not land[r][c]:
                continue
            if not land[r - 1][c]:
                add((c, r), (c + 1, r))
            if not land[r][c + 1]:
                add((c + 1, r), (c + 1, r + 1))
            if not land[r + 1][c]:
                add((c + 1, r + 1), (c, r + 1))
            if not land[r][c - 1]:
                add((c, r + 1), (c, r))
    rings = []
    while edges:
        start = next(iter(edges))
        ring = [start]
        here, heading = start, None
        while True:
            outs = edges[here]
            if heading is not None and len(outs) > 1:
                # Where two pieces touch at a corner: turn right, round
                # the same piece.
                right = (-heading[1], heading[0])
                outs.sort(key=lambda p: (p[0] - here[0],
                                         p[1] - here[1]) != right)
            nxt = outs.pop(0)
            if not outs:
                del edges[here]
            heading = (nxt[0] - here[0], nxt[1] - here[1])
            here = nxt
            if here == start:
                break
            ring.append(here)
        rings.append(ring)
    return rings


def _straight(ring):
    """`ring` without the corners on a straight run."""
    n = len(ring)
    out = []
    for i, (x, y) in enumerate(ring):
        (ax, ay), (bx, by) = ring[i - 1], ring[(i + 1) % n]
        if (x - ax) * (by - y) != (y - ay) * (bx - x):
            out.append((x, y))
    return out


def _area(pts) -> float:
    return abs(sum(ax * by - bx * ay for (ax, ay), (bx, by)
                   in zip(pts, pts[1:] + pts[:1]))) / 2


def _path(parts, tolerance: float) -> str:
    out = []
    for ring in parts:
        simple = simplify_ring(ring + ring[:1], tolerance)
        if simple is None:
            continue
        pts = [(round(x), round(y)) for x, y in simple[:-1]]
        pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        while len(pts) > 1 and pts[-1] == pts[0]:
            pts.pop()
        if len(pts) < 3:
            continue
        d = [f"M{pts[0][0]} {pts[0][1]}l"]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            d.append(f"{bx - ax} {by - ay} ")
        out.append("".join(d).rstrip() + "z")
    return "".join(out).replace(" -", "-")


def mini_outline(counties: list[list[list[tuple[float, float]]]]
                 ) -> dict | None:
    """The state's outer outline from its counties' rings (lon, lat):
    `{"width", "height", "path"}`, the path one SVG subpath per piece of
    land kept, in a box whose longer side is MINI_SIZE, at most
    MINI_BUDGET bytes. None if nothing is left."""
    counties = [rings for rings in counties if rings]
    if not counties:
        return None
    projected, w, h = _project(counties)
    cols = w * GRID + 2 * _PAD + 1
    rows = h * GRID + 2 * _PAD + 1
    land = _close(_paint(projected, cols, rows))
    _fill_holes(land)
    parts = []
    for ring in _trace(land):
        pts = [((x - _PAD) / GRID, (y - _PAD) / GRID) for x, y in _straight(ring)]
        if len(pts) >= 3:
            parts.append((_area(pts), pts))
    if not parts:
        return None
    parts.sort(key=lambda p: -p[0])
    kept = [pts for i, (area, pts) in enumerate(parts)
            if i == 0 or area >= MIN_PART_AREA]
    tolerance = MINI_TOLERANCE
    path = _path(kept, tolerance)
    while len(path) > MINI_BUDGET and tolerance < MINI_SIZE:
        tolerance *= 1.4
        path = _path(kept, tolerance)
    if not path:
        return None
    return {"width": w, "height": h, "path": path}
