"""Local measures (docs/ARCHITECTURE.md): county, city and school
district contests on a zip's ballot, end to end through the geo build,
the zip and address lookups, the ballot, the contest page and the
sitemap, over the fake San Diego of tests/geo_fixtures.py and the
fixture election in tests/fixtures/local/."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

import ballotreels.site.config as site_config
from ballotreels.geo.geocoder import lookup_address
from ballotreels.geo.lookup import GeoData, ocd_id, slug
from ballotreels.index import ballot_order, level_of, load_index
from ballotreels.site.server import build_deps, make_servers

from . import geo_fixtures
from .helpers import REPO
from .test_serve_public import ServerTestCase, _make_config

LOCAL_ELECTION = REPO / "tests" / "fixtures" / "local"
ELECTION_DIR = LOCAL_ELECTION / "ca-2026-11-03"
STATE = "ocd-division/country:us/state:ca"
SAN_DIEGO = f"{STATE}/county:san_diego"
IMPERIAL = f"{STATE}/county:imperial"
SD_CITY = f"{STATE}/place:san_diego"
EL_CAJON = f"{STATE}/place:el_cajon"
SD_UNIFIED = f"{STATE}/school_district:san_diego_unified_school_district"
CAJON_VALLEY = f"{STATE}/school_district:cajon_valley_union_school_district"
GROSSMONT = f"{STATE}/school_district:grossmont_union_high_school_district"


def _ids(levels):
    return [c["id"] for lvl in levels for c in lvl["contests"]]


class LocalServerTestCase(ServerTestCase):
    """The public and private listeners over the local fixture election
    and the fake San Diego's geo data."""

    def setUp(self):
        self._old_data_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = LOCAL_ELECTION
        self.addCleanup(self._restore_data_root)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name) / "var"
        geo_fixtures.build_local_geo(self.data_dir)
        self.config = _make_config(self.data_dir)
        self.deps = build_deps(self.config)
        self.public, self.private = make_servers(self.deps)
        self.addCleanup(self.deps.queue.close)
        for srv in (self.public, self.private):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(self._shutdown)

    def get_json(self, path):
        resp, body = self.get(self.public_port, path)
        self.assertEqual(resp.status, 200, body)
        return json.loads(body)

    def ballot_for_zip(self, zip_code):
        """The ballot the app asks for once a zip needs no question: every
        division the zip answer lists."""
        doc = self.get_json(f"/api/zip/{zip_code}")
        self.assertEqual(doc["ambiguous"], [])
        query = "&".join(f"d={e['ocd_id']}" for entries in
                         doc["kinds"].values() for e in entries)
        return self.get_json(f"/api/ballot?{query}")


class LocalGeoTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        self.warnings = geo_fixtures.build_local_geo(self.data_dir)
        self.geo = GeoData.load(self.data_dir / "geo" / "ca")

    def ids(self, zip_code, kind):
        doc = self.geo.zip_districts(zip_code)
        return [e["ocd_id"] for e in doc["kinds"].get(kind, [])]


class LocalGeoBuildTest(LocalGeoTestCase):
    def test_ocd_ids(self):
        self.assertEqual(self.warnings, [])
        self.assertEqual(ocd_id("place", "0666000", "ca", "San Diego",
                                "San Diego city"),
                         (SD_CITY, "City of San Diego"))
        self.assertEqual(ocd_id("place", "0600000", "ca", "Paradise",
                                "Paradise town")[1], "Town of Paradise")
        self.assertEqual(
            ocd_id("school_district", "0634320", "ca",
                   "San Diego Unified School District"),
            (SD_UNIFIED, "San Diego Unified School District"))
        self.assertIsNone(ocd_id("school_district", "0699999", "ca",
                                 "School District Not Defined"))
        self.assertEqual(slug("La Cañada  Flintridge"),
                         "la_cañada_flintridge")
        self.assertEqual(slug("Prince George's"), "prince_georges")

    def test_cities_and_school_districts_of_a_zip(self):
        doc = self.geo.zip_districts("92101")
        self.assertEqual(doc["kinds"]["place"],
                         [{"ocd_id": SD_CITY, "name": "City of San Diego"}])
        self.assertEqual(self.ids("92101", "school_district"), [SD_UNIFIED])
        self.assertEqual(doc["ambiguous"], [])
        self.assertEqual(doc["partial"], [])

    def test_a_zip_across_cities_asks_nothing_and_marks_them_partial(self):
        doc = self.geo.zip_districts("92102")
        self.assertEqual(self.ids("92102", "place"), [SD_CITY, EL_CAJON])
        self.assertEqual(self.ids("92102", "school_district"),
                         [SD_UNIFIED, CAJON_VALLEY, GROSSMONT])
        self.assertEqual(doc["ambiguous"], [])
        self.assertEqual(sorted(doc["partial"]),
                         sorted([SD_CITY, EL_CAJON, SD_UNIFIED, CAJON_VALLEY,
                                 GROSSMONT]))

    def test_partly_unincorporated_zip(self):
        # Half El Cajon, half Spring Valley, a census-designated place,
        # which is no city; the elementary and secondary districts each
        # cover all of it.
        doc = self.geo.zip_districts("92103")
        self.assertEqual(self.ids("92103", "place"), [EL_CAJON])
        self.assertEqual(self.ids("92103", "school_district"),
                         [CAJON_VALLEY, GROSSMONT])
        self.assertEqual(doc["partial"], [EL_CAJON])

    def test_zip_in_no_city(self):
        doc = self.geo.zip_districts("92250")
        self.assertNotIn("place", doc["kinds"])
        self.assertNotIn("school_district", doc["kinds"])

    def test_shapes_for_the_address_fallback(self):
        self.assertIn(EL_CAJON, self.geo.district_shapes)
        self.assertNotIn(f"{STATE}/place:spring_valley",
                         self.geo.district_shapes)
        self.assertEqual(self.geo.names[GROSSMONT],
                         "Grossmont Union High School District")

    def test_without_elementary_or_secondary_layers(self):
        from ballotreels.geo.build import build, census_urls
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            geo_fixtures.write_local_source(src)
            urls = {**census_urls("ca"), **geo_fixtures.SLD_REL_URLS}
            names = {url: name for name, url in urls.items()}

            def fetch(url):
                name = names[url]
                if name in ("elsd.zip", "scsd.zip"):
                    raise OSError("404")
                if name.endswith(".zip"):
                    return geo_fixtures._zip_shapes(src, name[:-4])
                return (src / name).read_bytes()

            out = src / "out"
            warnings = build(out, "ca", fetch,
                             urls=geo_fixtures.SLD_REL_URLS)
            self.assertEqual(len(warnings), 2)
            self.assertIn("elsd.zip", warnings[0])
            geo = GeoData.load(out / "geo" / "ca")
            doc = geo.zip_districts("92102")
            self.assertEqual(
                [e["ocd_id"] for e in doc["kinds"]["school_district"]],
                [SD_UNIFIED])


def _geocoder(geographies, x=12.0, y=5.0):
    doc = {"result": {"addressMatches": [{
        "matchedAddress": "1 MAIN ST, EL CAJON, CA, 92102",
        "coordinates": {"x": x, "y": y},
        "geographies": {
            "States": [{"GEOID": "06"}],
            "Counties": [{"GEOID": "06073", "NAME": "San Diego County",
                          "BASENAME": "San Diego"}],
            **geographies}}]}}
    return lambda url: json.dumps(doc)


class LocalAddressTest(LocalGeoTestCase):
    def test_address_names_its_city_and_school_districts(self):
        fetch = _geocoder({
            "Incorporated Places": [{"GEOID": "0621712",
                                     "NAME": "El Cajon city",
                                     "BASENAME": "El Cajon"}],
            "Census Designated Places": [],
            "Unified School Districts": [],
            "Elementary School Districts": [{
                "GEOID": "0606540",
                "NAME": "Cajon Valley Union School District"}],
            "Secondary School Districts": [{
                "GEOID": "0616050",
                "NAME": "Grossmont Union High School District"}],
        })
        result = lookup_address("1 Main St", fetch, "https://x.test",
                                {"ca": self.geo})
        self.assertEqual(result["kinds"]["place"],
                         [{"ocd_id": EL_CAJON, "name": "City of El Cajon"}])
        self.assertEqual(
            [e["ocd_id"] for e in result["kinds"]["school_district"]],
            [CAJON_VALLEY, GROSSMONT])

    def test_unincorporated_address_has_no_city(self):
        fetch = _geocoder({"Incorporated Places": [],
                           "Unified School Districts": []}, x=16.0)
        result = lookup_address("1 Main St", fetch, "https://x.test",
                                {"ca": self.geo})
        self.assertNotIn("place", result["kinds"])

    def test_missing_layers_fall_back_to_the_shapes(self):
        result = lookup_address("1 Main St", _geocoder({}, x=5.0),
                                "https://x.test", {"ca": self.geo})
        self.assertEqual([e["ocd_id"] for e in result["kinds"]["place"]],
                         [SD_CITY])
        self.assertEqual(
            [e["ocd_id"] for e in result["kinds"]["school_district"]],
            [SD_UNIFIED])


class CountyIndexTest(unittest.TestCase):
    def test_county_level_after_the_state(self):
        index = load_index(ELECTION_DIR)
        self.assertEqual(level_of(SAN_DIEGO, STATE), "county")
        self.assertEqual(
            [e.id for e in ballot_order(index)],
            ["ca-2026-11-03-prop-90", "ca-2026-11-03-prop-91",
             "ca-2026-11-03-sd-county-measure-a",
             "ca-2026-11-03-sd-county-measure-b",
             "ca-2026-11-03-imperial-county-measure-c"])

    def test_crash_course_stays_statewide(self):
        index = load_index(ELECTION_DIR)
        self.assertEqual(index.crash_course.members,
                         ("ca-2026-11-03-prop-90", "ca-2026-11-03-prop-91"))


class CountyEndToEndTest(LocalServerTestCase):
    def test_zip_names_its_county(self):
        doc = self.get_json("/api/zip/92101")
        self.assertEqual(doc["kinds"]["county"],
                         [{"ocd_id": SAN_DIEGO, "name": "San Diego County"}])
        doc = self.get_json("/api/zip/92250")
        self.assertEqual([e["ocd_id"] for e in doc["kinds"]["county"]],
                         [IMPERIAL])

    def test_ballot_has_its_county_measures_only(self):
        doc = self.ballot_for_zip("92101")
        self.assertEqual([lvl["level"] for lvl in doc["levels"]],
                         ["state", "county"])
        self.assertEqual(_ids(doc["levels"][1:]),
                         ["ca-2026-11-03-sd-county-measure-a",
                          "ca-2026-11-03-sd-county-measure-b"])
        doc = self.ballot_for_zip("92250")
        self.assertEqual(_ids(doc["levels"][1:]),
                         ["ca-2026-11-03-imperial-county-measure-c"])

    def test_contest_page(self):
        summary = self.ballot_for_zip("92101")["levels"][1]["contests"][0]
        self.assertEqual(summary["path"], "/ca/2026/sd-county-measure-a")
        self.assertEqual(summary["status"], "none")
        doc = self.get_json("/api/contest/ca/2026/sd-county-measure-a")
        self.assertEqual(doc["id"], "ca-2026-11-03-sd-county-measure-a")
        self.assertIsNotNone(doc["template_version"])
        resp, body = self.get(self.public_port,
                              "/ca/2026/sd-county-measure-a")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"Fake County Sales Tax", body)

    def test_state_page_and_sitemap(self):
        doc = self.get_json("/api/state/ca")
        self.assertEqual(_ids(doc["levels"]),
                         ["ca-2026-11-03-prop-90", "ca-2026-11-03-prop-91"])
        resp, body = self.get(self.public_port, "/sitemap.xml")
        self.assertIn(b"/ca/2026/sd-county-measure-a", body)


if __name__ == "__main__":
    unittest.main()
