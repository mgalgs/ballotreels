"""Polygon simplification and point-in-polygon, no library needed."""

from __future__ import annotations

import math

Point = tuple[float, float]
Ring = tuple[Point, ...]


def _perp_distance(p: Point, a: Point, b: Point) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    num = abs((x - x1) * dy - (y - y1) * dx)
    den = math.hypot(dx, dy)
    return num / den


def douglas_peucker(points: list[Point], tolerance: float) -> list[Point]:
    """Simplify an open path, keeping both endpoints and dropping any
    point within `tolerance` of the line between the points that survive
    around it."""
    points = list(points)
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    max_dist = -1.0
    index = 0
    for i in range(1, len(points) - 1):
        d = _perp_distance(points[i], start, end)
        if d > max_dist:
            max_dist = d
            index = i
    if max_dist > tolerance:
        left = douglas_peucker(points[:index + 1], tolerance)
        right = douglas_peucker(points[index:], tolerance)
        return left[:-1] + right
    return [start, end]


def simplify_ring(ring: Ring, tolerance: float) -> list[Point] | None:
    """Simplify a closed ring: Douglas-Peucker, coordinates rounded to 5
    decimals, duplicate points from rounding collapsed, and the ring
    re-closed. Returns None if what is left has fewer than 4 points (not
    enough to be a ring)."""
    if len(ring) < 2:
        return None
    simplified = douglas_peucker(list(ring), tolerance)
    rounded = [(round(x, 5), round(y, 5)) for x, y in simplified]
    deduped = [rounded[0]]
    for p in rounded[1:]:
        if p != deduped[-1]:
            deduped.append(p)
    if deduped[0] != deduped[-1]:
        deduped.append(deduped[0])
    if len(deduped) < 4:
        return None
    return deduped


def _point_in_ring(x: float, y: float, ring: Ring) -> bool:
    inside = False
    x1, y1 = ring[-1]
    for x2, y2 in ring:
        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                inside = not inside
        x1, y1 = x2, y2
    return inside


def point_in_polygon(point: Point, rings: list[Ring]) -> bool:
    """True if `point` is inside the shape described by `rings`: a point
    in an odd number of rings is inside (handles holes and several
    disjoint parts without needing to tell outer rings from holes)."""
    x, y = point
    count = 0
    for ring in rings:
        if len(ring) >= 3 and _point_in_ring(x, y, ring):
            count += 1
    return count % 2 == 1


def bbox(rings: list[Ring]) -> tuple[float, float, float, float]:
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    return (min(xs), min(ys), max(xs), max(ys))
