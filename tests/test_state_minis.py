"""The home page's state icons: each state's coarse outer outline
(ballotreels.geo.outline, written into counties.json's `mini`), over
hand-made county shapes (nothing here is real geography)."""

import math
import re
import unittest

from ballotreels.geo.counties import county_doc
from ballotreels.geo.outline import MINI_BUDGET, MINI_SIZE, mini_outline

from .helpers import REPO

FIXTURE_GEO = REPO / "tests" / "fixtures" / "counties" / "geo" / "ca"


def _square(x, y, w, h=None):
    h = w if h is None else h
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def _parts(path):
    """The path's subpaths, each as its absolute points."""
    out = []
    for sub in re.findall(r"M[^Mz]*z", path):
        nums = [int(n) for n in re.findall(r"-?\d+", sub)]
        x, y = nums[0], nums[1]
        pts = [(x, y)]
        for dx, dy in zip(nums[2::2], nums[3::2]):
            x, y = x + dx, y + dy
            pts.append((x, y))
        out.append(pts)
    return out


class MiniOutlineTest(unittest.TestCase):
    def test_two_counties_sharing_an_edge_make_one_outline(self):
        # Two 1-degree squares side by side near the equator (so the
        # outline's box is about 2:1): no line between them.
        mini = mini_outline([[_square(0, 0, 1)], [_square(1, 0, 1)]])
        self.assertEqual((mini["width"], mini["height"]), (MINI_SIZE, 50))
        parts = _parts(mini["path"])
        self.assertEqual(len(parts), 1)
        self.assertEqual(sorted(set(parts[0])),
                         [(0, 0), (0, 50), (100, 0), (100, 50)])

    def test_neighbours_simplified_apart_leave_no_line(self):
        # The shared edge drawn twice, each a hair off (a gap, then an
        # overlap): still one shape with no notch inside.
        left = [(0, 0), (1.0004, 0), (0.9997, 0.5), (1.0003, 1), (0, 1),
                (0, 0)]
        right = [(0.9998, 0), (2, 0), (2, 1), (0.9996, 1), (1.0004, 0.5),
                 (0.9998, 0)]
        parts = _parts(mini_outline([[left], [right]])["path"])
        self.assertEqual(len(parts), 1)
        self.assertEqual(sorted(set(parts[0])),
                         [(0, 0), (0, 50), (100, 0), (100, 50)])

    def test_a_lake_inside_is_filled(self):
        ring = _square(0, 0, 2)
        lake = _square(0.5, 0.5, 1)
        parts = _parts(mini_outline([[ring, lake]])["path"])
        self.assertEqual(len(parts), 1)

    def test_separate_pieces_of_land_are_kept(self):
        # A mainland and an island a third its size, across water.
        mini = mini_outline([[_square(0, 0, 2)], [_square(3, 0, 1)]])
        parts = _parts(mini["path"])
        self.assertEqual(len(parts), 2)
        xs = sorted(min(x for x, _ in p) for p in parts)
        self.assertEqual(xs, [0, 75])

    def test_a_tiny_island_is_dropped(self):
        # 0.03 degrees across: under a unit at icon size.
        mini = mini_outline([[_square(0, 0, 2)], [_square(2.5, 1, 0.03)],
                             [_square(2.5, 0, 0.08)]])
        parts = _parts(mini["path"])
        self.assertEqual(len(parts), 1)
        self.assertEqual(max(x for x, _ in parts[0]), 78)
        # the box is still the state's, island and all
        self.assertEqual(mini["width"], MINI_SIZE)

    def test_a_lone_tiny_county_is_still_drawn(self):
        mini = mini_outline([[_square(0, 0, 0.01)]])
        self.assertEqual(len(_parts(mini["path"])), 1)

    def test_a_ragged_coast_fits_the_budget(self):
        # A coast of 4000 points, jagged at every scale (too much path
        # at the first tolerance, so it loosens), and a string of
        # islands big enough to keep.
        coast = []
        for i in range(4000):
            t = 2 * math.pi * i / 4000
            r = 3 + 0.4 * math.sin(97 * t) + 0.15 * math.sin(301 * t) \
                + 0.05 * math.sin(1999 * t)
            coast.append((r * math.cos(t), r * math.sin(t)))
        coast.append(coast[0])
        islands = [[_square(4 + 1.3 * i, -3 + 0.5 * i, 1.0)]
                   for i in range(8)]
        mini = mini_outline([[coast]] + islands)
        self.assertLessEqual(len(mini["path"]), MINI_BUDGET)
        parts = _parts(mini["path"])
        self.assertGreaterEqual(len(parts), 2)
        self.assertGreater(len(parts[0]), 20)
        for x, y in (p for part in parts for p in part):
            self.assertTrue(0 <= x <= mini["width"], (x, y))
            self.assertTrue(0 <= y <= mini["height"], (x, y))

    def test_no_counties_no_outline(self):
        self.assertIsNone(mini_outline([]))

    def test_counties_json_carries_the_outline(self):
        doc = county_doc(FIXTURE_GEO)
        mini = doc["mini"]
        self.assertEqual(set(mini), {"width", "height", "path"})
        self.assertEqual(mini["width"], MINI_SIZE)
        self.assertEqual(len(_parts(mini["path"])), 1)
        # the outer edge only: smaller than any one county's hero path
        self.assertLess(len(mini["path"]),
                        min(map(len, doc["hero"]["paths"].values())) * 2)
