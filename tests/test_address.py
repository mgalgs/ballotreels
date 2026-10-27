import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ballotreels.geo.geocoder import (AddressNotFound, GeocoderError,
                                      lookup_address)
from ballotreels.geo.lookup import GeoData

from . import geo_fixtures
from .helpers import REPO

FIXTURES = REPO / "tests" / "fixtures" / "geocoder"
BASE_URL = "https://geocoder.example.test"


def _fetch_fixture(name: str):
    text = (FIXTURES / name).read_text(encoding="utf-8")

    def fetch(url: str) -> str:
        return text

    return fetch


class AddressLookupTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        geo_fixtures.build_fixture_geo(self.data_dir)
        self.geo = GeoData.load(self.data_dir / "geo" / "ca")


class ExactMatchTest(AddressLookupTestCase):
    def test_address_exact(self):
        result = lookup_address("123 Fake St", _fetch_fixture("full.json"),
                                BASE_URL, {"ca": self.geo})
        self.assertEqual(result["matched_address"],
                         "123 FAKE ST, EXAMPLE, CA, 99999")
        self.assertEqual(result["kinds"]["cd"],
                         [{"ocd_id": "ocd-division/country:us/state:ca/cd:1",
                          "name": "Congressional District 1"}])
        self.assertEqual(result["kinds"]["sldu"], [{
            "ocd_id": "ocd-division/country:us/state:ca/sldu:1",
            "name": "State Senate District 1"}])
        self.assertEqual(result["kinds"]["sldl"], [{
            "ocd_id": "ocd-division/country:us/state:ca/sldl:1",
            "name": "State Assembly District 1"}])
        self.assertEqual(result["kinds"]["county"], [{
            "ocd_id": "ocd-division/country:us/state:ca/county:example",
            "name": "Example County"}])


class FallbackTest(AddressLookupTestCase):
    def test_address_fallback_point_in_polygon(self):
        result = lookup_address(
            "123 Fake St", _fetch_fixture("missing_sldl.json"), BASE_URL,
            {"ca": self.geo})
        # The fixture point (5, 5) falls inside the fake sldl:1 square
        # (0,0)-(20,10); point-in-polygon fills in the missing layer.
        self.assertIn("sldl", result["kinds"])
        self.assertEqual(result["kinds"]["sldl"][0]["ocd_id"],
                         "ocd-division/country:us/state:ca/sldl:1")
        # The present layers are unaffected.
        self.assertEqual(result["kinds"]["cd"][0]["ocd_id"],
                         "ocd-division/country:us/state:ca/cd:1")


class StateTest(AddressLookupTestCase):
    def test_address_in_another_state_not_found(self):
        import json
        doc = {"result": {"addressMatches": [{
            "matchedAddress": "1 FAKE ST, EXAMPLE, NV, 99999",
            "coordinates": {"x": 5.0, "y": 5.0},
            "geographies": {
                "States": [{"GEOID": "32", "STUSAB": "NV"}],
                "119th Congressional Districts": [{"GEOID": "3201"}],
            }}]}}
        with self.assertRaises(AddressNotFound):
            lookup_address("1 Fake St", lambda url: json.dumps(doc),
                           BASE_URL, {"ca": self.geo})


class ErrorsTest(AddressLookupTestCase):
    def test_address_errors(self):
        # The geocoder's error detail is logged to stderr; keep it out of
        # the test output.
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        with self.subTest("no match"):
            with self.assertRaises(AddressNotFound):
                lookup_address("nowhere", _fetch_fixture("no_match.json"),
                               BASE_URL, {"ca": self.geo})

        with self.subTest("geocoder error"):
            def failing_fetch(url):
                raise OSError("connection refused")
            with self.assertRaises(GeocoderError):
                lookup_address("123 Fake St", failing_fetch, BASE_URL,
                               {"ca": self.geo})

        with self.subTest("timeout"):
            def timeout_fetch(url):
                raise TimeoutError("timed out")
            with self.assertRaises(GeocoderError):
                lookup_address("123 Fake St", timeout_fetch, BASE_URL,
                               {"ca": self.geo})


if __name__ == "__main__":
    unittest.main()
