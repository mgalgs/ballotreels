"""County pages (/<st>/<year>/county/<county>): which cities and school
districts each county holds (ballotreels.geo.counties, from the built
shapes), and the pages themselves, over the fake counties of
tests/fixtures/counties/ (see its contests.toml)."""

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ballotreels.cli import main as cli_main
from ballotreels.geo.counties import FILENAME, county_doc, write_counties

from . import geo_fixtures
from .helpers import REPO

FIXTURE = REPO / "tests" / "fixtures" / "counties"
FIXTURE_GEO = FIXTURE / "geo" / "ca"
STATE = "ocd-division/country:us/state:ca"
ALPHA = f"{STATE}/county:alpha"
BETA = f"{STATE}/county:beta"
GAMMA = f"{STATE}/county:gamma"
DELTA = f"{STATE}/county:delta"
TWIN_VALLEY = f"{STATE}/school_district:twin_valley_unified_school_district"


def _counties_of(doc, division):
    return [c for c, entry in doc["counties"].items()
            if division in entry["divisions"]]


class CountyMembershipTest(unittest.TestCase):
    def setUp(self):
        self.doc = county_doc(FIXTURE_GEO)

    def test_a_city_is_in_its_county(self):
        self.assertEqual(_counties_of(self.doc, f"{STATE}/place:alphaville"),
                         [ALPHA])

    def test_a_district_across_a_county_line_is_in_both(self):
        self.assertEqual(_counties_of(self.doc, TWIN_VALLEY), [ALPHA, BETA])

    def test_touching_a_county_line_is_not_being_in_the_county(self):
        self.assertEqual(_counties_of(self.doc, f"{STATE}/place:edgetown"),
                         [BETA])

    def test_a_sliver_across_a_county_line_does_not_count(self):
        # Sliverton crosses Gamma's line by 0.0008 degrees east-west,
        # Northedge Delta's by as much north-south: outline mismatch.
        self.assertEqual(_counties_of(self.doc, f"{STATE}/place:sliverton"),
                         [BETA])
        self.assertEqual(_counties_of(self.doc, f"{STATE}/place:northedge"),
                         [ALPHA])

    def test_a_district_too_small_to_measure_is_in_its_county(self):
        tiny = f"{STATE}/school_district:pinpoint_elementary_school_district"
        self.assertEqual(_counties_of(self.doc, tiny), [GAMMA])

    def test_every_county_is_listed_even_with_nothing_in_it(self):
        self.assertEqual(list(self.doc["counties"]),
                         [ALPHA, BETA, DELTA, GAMMA])
        self.assertEqual(self.doc["counties"][DELTA],
                         {"name": "Delta County", "divisions": []})

    def test_secondary_only_territory_counts_as_its_district(self):
        with tempfile.TemporaryDirectory() as tmp:
            geo = Path(tmp)
            shutil.copytree(FIXTURE_GEO, geo, dirs_exist_ok=True)
            path = geo / "school_district.geojson"
            doc = json.loads(path.read_text(encoding="utf-8"))
            feature = json.loads(json.dumps(doc["features"][0]))
            feature["properties"]["ocd_id"] = TWIN_VALLEY + "_9-12"
            feature["geometry"]["coordinates"] = [[
                [-119.9, 38.1], [-119.5, 38.1], [-119.5, 38.3],
                [-119.9, 38.3], [-119.9, 38.1]]]
            doc["features"].append(feature)
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertEqual(_counties_of(county_doc(geo), TWIN_VALLEY),
                             [ALPHA, BETA, GAMMA])

    def test_hero_outlines(self):
        hero = self.doc["hero"]
        self.assertEqual(set(hero["paths"]), {ALPHA, BETA, GAMMA, DELTA})
        # longitude squashed by cos(39 degrees): wider than tall, not 3:2
        self.assertEqual(hero["width"], 1000)
        self.assertEqual(hero["height"], 858)
        self.assertEqual(hero["paths"][DELTA], "M0 429l333 0 0-429-333 0z")


class CountiesFileTest(unittest.TestCase):
    def test_geo_build_writes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            geo_fixtures.build_local_geo(Path(tmp))
            doc = json.loads((Path(tmp) / "geo" / "ca" / FILENAME)
                             .read_text(encoding="utf-8"))
        sd = doc["counties"][f"{STATE}/county:san_diego"]["divisions"]
        self.assertIn(f"{STATE}/place:el_cajon", sd)
        self.assertEqual(
            doc["counties"][f"{STATE}/county:imperial"]["divisions"], [])

    def test_geo_counties_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            geo = Path(tmp) / "geo" / "ca"
            shutil.copytree(FIXTURE_GEO, geo)
            out = io.StringIO()
            self.assertEqual(cli_main(["geo", "counties", "--state", "ca",
                                       "--data-dir", tmp], out=out), 0)
            self.assertIn(f"{geo / FILENAME}: written", out.getvalue())
            self.assertEqual(json.loads((geo / FILENAME).read_text(
                encoding="utf-8")), county_doc(FIXTURE_GEO))
            # no build there: says so, writes nothing
            out = io.StringIO()
            self.assertEqual(cli_main(["geo", "counties", "--state", "ut",
                                       "--data-dir", tmp], out=out), 1)
            self.assertIn("geo build", out.getvalue())

    def test_write_counties_returns_its_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURE_GEO, tmp, dirs_exist_ok=True)
            self.assertEqual(write_counties(tmp), Path(tmp) / FILENAME)


if __name__ == "__main__":
    unittest.main()
