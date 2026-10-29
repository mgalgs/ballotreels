"""Far, tiny outliers (ballotreels.geo.outline.drawn) left out of both
of a state's drawings, the state page's hero and the home page's mini,
over hand-made shapes (nothing here is real geography): a main body, a
near chain of specks that stays, far specks that go and a far big
piece that stays; and a Hawaii-shaped state whose far chain goes."""

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


# Shaped like Hawaii (not its outlines): main blobs from longitude
# -160.2 to -155.0, and a sparse chain of one county's specks from
# -161.9, 1.7 degrees past the west end, to -178.4, holding about 10%
# of the area.
HI_BIG = [_square(-156.0, 18.9, 1.0)]
HI_MAUI = [_square(-156.7, 20.6, 0.55), _square(-157.1, 21.0, 0.35),
           _square(-156.8, 20.3, 0.28)]
HI_KAUAI = [_square(-159.7, 21.8, 0.45), _square(-160.2, 21.8, 0.15)]
HI_KALAWAO = [_square(-157.0, 21.2, 0.1)]
HI_CHAIN = [_square(x, y, 0.16) for x, y in
            ((-161.9, 23.0), (-164.7, 23.5), (-166.3, 23.8),
             (-168.0, 24.9), (-171.7, 25.7), (-173.9, 26.0),
             (-175.9, 27.7), (-178.4, 28.3))]
HI_HONOLULU = [_square(-158.3, 21.2, 0.5)] + HI_CHAIN


class HawaiiShapedTest(unittest.TestCase):
    def test_the_chain_goes_and_every_main_blob_stays(self):
        counties = [HI_BIG, HI_MAUI, HI_KAUAI, HI_KALAWAO, HI_HONOLULU]
        self.assertEqual(drawn(counties),
                         [HI_BIG, HI_MAUI, HI_KAUAI, HI_KALAWAO,
                          HI_HONOLULU[:1]])

    def test_the_chain_holds_about_a_tenth(self):
        # The fixture means what it says: the chain is ~10% of the area,
        # far over round 1's 0.5%.
        area = lambda r: (r[1][0] - r[0][0]) ** 2
        rings = HI_BIG + HI_MAUI + HI_KAUAI + HI_KALAWAO + HI_HONOLULU
        share = sum(map(area, HI_CHAIN)) / sum(map(area, rings))
        self.assertGreater(share, 0.08)
        self.assertLess(share, 0.12)

    def test_the_hero_and_mini_frame_the_main_islands(self):
        doc = _doc({f"{STATE}/county:{n}": rings for n, rings in
                    (("big", HI_BIG), ("maui", HI_MAUI),
                     ("kauai", HI_KAUAI), ("kalawao", HI_KALAWAO),
                     ("honolulu", HI_HONOLULU))})
        hero = doc["hero"]
        # x -160.2 to -155.0, y 18.9 to 22.25
        squash = math.cos(math.radians((18.9 + 22.25) / 2))
        self.assertEqual(hero["width"], 1000)
        self.assertEqual(hero["height"],
                         round(3.35 / (5.2 * squash) * 1000))
        self.assertEqual(
            len(_parts(hero["paths"][f"{STATE}/county:honolulu"])), 1)
        self.assertEqual((doc["mini"]["width"], doc["mini"]["height"]),
                         (100, round(3.35 / (5.2 * squash) * 100)))


class FarthestFirstTest(unittest.TestCase):
    def test_a_far_big_piece_over_the_share_stays(self):
        # 2-degree square well east: 20% of the area.
        counties = [[BODY], [_square(7, 1, 2)]]
        self.assertIs(drawn(counties), counties)

    def test_a_far_speck_nearer_than_a_far_big_piece_stays(self):
        # The far big piece is the farthest ring and over the share, so
        # no run of the farthest qualifies: the speck north of the body,
        # far from it but nearer the middle than the big piece, stays.
        counties = [[BODY], [_square(7, 1, 2)], [_square(2, 6.3, 0.05)]]
        self.assertIs(drawn(counties), counties)

    def test_a_far_speck_beyond_a_far_big_piece_goes(self):
        speck = _square(12, 2, 0.05)
        self.assertEqual(drawn([[BODY], [_square(7, 1, 2)], [speck]]),
                         [[BODY], [_square(7, 1, 2)], []])

    def test_a_near_chain_stays(self):
        counties = [[BODY], NEAR_CHAIN]
        self.assertIs(drawn(counties), counties)

    def test_far_specks_in_different_directions_both_go(self):
        east = _square(9, 2, 0.05)
        south = _square(2, -5, 0.05)
        self.assertEqual(drawn([[BODY, east], [south], NEAR_CHAIN]),
                         [[BODY], [], NEAR_CHAIN])

    def test_a_far_speck_beside_a_near_one_stays_with_it(self):
        # Two specks, the farther far out, the nearer just off the body:
        # the nearer is never dropped, the farther still is.
        far = _square(-3, 2, 0.05)
        near = _square(-0.3, 2, 0.05)
        self.assertEqual(drawn([[BODY, far, near]]), [[BODY, near]])


if __name__ == "__main__":
    unittest.main()
