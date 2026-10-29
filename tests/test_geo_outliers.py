"""Far, tiny outliers (ballotreels.geo.outline.drawn) left out of both
of a state's drawings, the state page's hero and the home page's mini,
over hand-made shapes (nothing here is real geography): a main body, a
near chain of specks that stays, a far speck that goes and a far big
piece that stays."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ballotreels.geo import counties as counties_mod
from ballotreels.geo.counties import county_doc
from ballotreels.geo.outline import drawn

from .test_state_minis import FIXTURE_GEO, _parts, _square

STATE = "ocd-division/country:us/state:zz"
MAIN = f"{STATE}/county:main"
CHAIN = f"{STATE}/county:chain"
BIG = f"{STATE}/county:big"
SPECK = f"{STATE}/county:speck"

# The main body: a 4-degree square on the equator.
BODY = _square(0, 0, 4)
# Specks 0.05 degrees across, 0.2 to 0.4 east of it: near.
NEAR_CHAIN = [_square(4.2, 1, 0.05), _square(4.3, 2, 0.05),
              _square(4.4, 3, 0.05)]
# A speck 3 degrees west of it, part of the main county: far.
FAR_SPECK = _square(-3, 2, 0.05)
# A county that is only a speck 3 degrees north of it: far.
LONE_SPECK = _square(2, 7, 0.05)
# A 2-degree square 2 degrees east: far, but at 20% of the area too big
# to be an outlier; nearer the middle than the specks, so it does not
# shield them.
FAR_BIG = _square(6, 1, 2)


def _doc(counties):
    with tempfile.TemporaryDirectory() as tmp:
        geo = Path(tmp)
        (geo / "county.geojson").write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [{"type": "Feature",
                          "properties": {"ocd_id": ocd_id, "name": ocd_id},
                          "geometry": {"type": "Polygon",
                                       "coordinates": rings}}
                         for ocd_id, rings in counties.items()]}),
            encoding="utf-8")
        return county_doc(geo)


def _height(width_deg, height_deg, size):
    """The box's height for a box `width_deg` by `height_deg` from the
    equator up, its width the longer side."""
    squash = math.cos(math.radians(height_deg / 2))
    return round(height_deg / (width_deg * squash) * size)


def _hero_xs(path):
    return [x for part in _parts(path) for x, _ in part]


class OutliersTest(unittest.TestCase):
    def setUp(self):
        self.doc = _doc({MAIN: [BODY, FAR_SPECK], CHAIN: NEAR_CHAIN,
                         BIG: [FAR_BIG], SPECK: [LONE_SPECK]})

    def test_the_hero_frames_the_body_and_its_far_big_piece(self):
        hero = self.doc["hero"]
        # x 0 to 8, y 0 to 4: neither speck in the box
        self.assertEqual((hero["width"], hero["height"]),
                         (1000, _height(8, 4, 1000)))
        self.assertEqual(len(_parts(hero["paths"][MAIN])), 1)
        self.assertEqual(min(_hero_xs(hero["paths"][MAIN])), 0)
        self.assertEqual(len(_parts(hero["paths"][CHAIN])), 3)
        self.assertEqual(max(_hero_xs(hero["paths"][BIG])), 1000)

    def test_a_county_only_of_outliers_is_listed_without_a_path(self):
        self.assertIn(SPECK, self.doc["counties"])
        self.assertNotIn(SPECK, self.doc["hero"]["paths"])

    def test_the_mini_frames_the_same(self):
        mini = self.doc["mini"]
        self.assertEqual((mini["width"], mini["height"]),
                         (100, _height(8, 4, 100)))
        parts = _parts(mini["path"])
        self.assertEqual(len(parts), 2)
        self.assertEqual(sorted(min(x for x, _ in p) for p in parts),
                         [0, 75])


class NearChainTest(unittest.TestCase):
    """The body and the near chain alone: the chain is in the box."""

    def setUp(self):
        self.doc = _doc({MAIN: [BODY, FAR_SPECK], CHAIN: NEAR_CHAIN})

    def test_the_hero_reaches_the_chain(self):
        hero = self.doc["hero"]
        self.assertEqual((hero["width"], hero["height"]),
                         (1000, _height(4.45, 4, 1000)))
        self.assertEqual(max(_hero_xs(hero["paths"][CHAIN])), 1000)

    def test_the_mini_reaches_the_chain(self):
        mini = self.doc["mini"]
        self.assertEqual((mini["width"], mini["height"]),
                         (100, _height(4.45, 4, 100)))


class NoOutliersTest(unittest.TestCase):
    """A state with nothing far and tiny is drawn as it was before the
    rule: byte for byte the drawings made without it."""

    def assert_unchanged(self, make_doc):
        doc = make_doc()
        with mock.patch.object(counties_mod, "drawn", lambda c: c), \
                mock.patch("ballotreels.geo.outline.drawn", lambda c: c):
            before = make_doc()
        self.assertEqual(json.dumps(doc), json.dumps(before))

    def test_the_fixture_state(self):
        self.assert_unchanged(lambda: county_doc(FIXTURE_GEO))

    def test_a_near_chain_and_a_far_big_piece(self):
        self.assert_unchanged(lambda: _doc(
            {MAIN: [BODY], CHAIN: NEAR_CHAIN, BIG: [FAR_BIG]}))

    def test_drawn_hands_back_the_counties_themselves(self):
        counties = [[BODY], NEAR_CHAIN, [FAR_BIG]]
        self.assertIs(drawn(counties), counties)


class DrawnTest(unittest.TestCase):
    def test_only_the_far_specks_go(self):
        self.assertEqual(
            drawn([[BODY, FAR_SPECK], NEAR_CHAIN, [FAR_BIG], [LONE_SPECK]]),
            [[BODY], NEAR_CHAIN, [FAR_BIG], []])

    def test_a_far_piece_over_the_share_stays(self):
        # Alone with the body, a 1.8-degree island is 17% of the area.
        island = _square(-3, 2, 1.8)
        counties = [[BODY, island]]
        self.assertIs(drawn(counties), counties)


if __name__ == "__main__":
    unittest.main()
