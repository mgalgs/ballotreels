"""One serve process, several states' elections (fake fixtures: none of
this is real data)."""

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path

import ballotreels.site.config as site_config
from ballotreels.geo.lookup import ocd_id
from ballotreels.site.config import ElectionResolutionError
from ballotreels.site.server import build_deps, make_servers

from . import geo_fixtures
from .test_serve_private import PrivateApiMixin
from .test_serve_public import _make_config

# 10001 is New York's alone; 99902 is (in these fixtures) in both the
# fake California's data and the fake New York's, as a zip on a state
# line is in both states' Census files.
NY_ZIPS = ["10001", "99902"]


def _write_election(root: Path, election_id: str, state: str,
                    contests: list[tuple[str, str, str]]) -> None:
    """`contests`: (id suffix, division suffix, title) per measure."""
    division = f"ocd-division/country:us/state:{state}"
    lines = ["[election]", f'id = "{election_id}"', f'state = "{division}"',
             'title = "Test Election"', ""]
    for i, (suffix, sub, title) in enumerate(contests, start=1):
        lines += ["[[contest]]", f'id = "{election_id}-{suffix}"',
                  'kind = "measure"', f'division = "{division}{sub}"',
                  f'title = "{title}"', f'number = "{i}"', ""]
    (root / election_id).mkdir(parents=True)
    (root / election_id / "contests.toml").write_text(
        "\n".join(lines), encoding="utf-8")


def _geocoder_doc(state_fips: str, extra: dict | None = None) -> str:
    geographies = {"States": [{"GEOID": state_fips}],
                   "119th Congressional Districts": [
                       {"GEOID": state_fips + "01"}]}
    geographies.update(extra or {})
    return json.dumps({"result": {"addressMatches": [{
        "matchedAddress": "1 FAKE ST, EXAMPLE",
        "coordinates": {"x": 1.2, "y": 1.2},
        "geographies": geographies}]}})


class MultiStateTestCase(PrivateApiMixin, unittest.TestCase):
    def setUp(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = tmp / "data"
        _write_election(self.root, "ca-2026-11-03", "ca", [
            ("prop-1", "", "Proposition 1: Fake California Measure"),
            ("cd-1", "/cd:1", "Fake California District Measure")])
        _write_election(self.root, "ny-2026-11-03", "ny", [
            ("prop-1", "", "Proposal 1: Fake New York Measure"),
            ("sldl-1", "/sldl:1", "Fake Assembly District Measure")])
        _write_election(self.root, "tx-2026-11-03", "tx", [
            ("prop-1", "", "Proposition 1: Fake Texas Measure")])
        old_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = self.root
        self.addCleanup(setattr, site_config, "DATA_ROOT", old_root)

        self.data_dir = tmp / "var"
        geo_fixtures.build_fixture_geo(self.data_dir)
        geo_fixtures.build_simple_state_geo(self.data_dir, "ny", NY_ZIPS)
        # No geo data for Texas: a warning, not a failure.
        self.warnings = []
        self.deps = build_deps(_make_config(self.data_dir, election=None),
                               warn=self.warnings.append)
        self.addCleanup(self.deps.queue.close)
        self.public, self.private = make_servers(self.deps)
        for srv in (self.public, self.private):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        for srv in (self.public, self.private):
            srv.shutdown()
            srv.server_close()

    @property
    def public_port(self):
        return self.public.server_address[1]

    @property
    def private_port(self):
        return self.private.server_address[1]

    def get(self, path):
        status, body, _ = self._public("GET", path)
        return status, body


class LoadTest(MultiStateTestCase):
    def test_every_election_loaded(self):
        self.assertEqual(sorted(self.deps.states), ["ca", "ny", "tx"])
        self.assertIsNone(self.deps.states["tx"].geo)
        self.assertEqual(len(self.warnings), 1)
        self.assertIn("'tx'", self.warnings[0])

    def test_election_restricts(self):
        for value in ("ny-2026-11-03", "ny-2026-11-03, ca-2026-11-03"):
            with self.subTest(value):
                config = _make_config(self.data_dir, election=value)
                from ballotreels.site.server import load_states
                states = load_states(config, warn=lambda m: None)
                self.assertEqual(sorted(states),
                                 sorted(v.strip()[:2] for v in value.split(",")))

    def test_repeated_election_flag(self):
        import argparse
        from ballotreels.site.config import load_config
        ns = argparse.Namespace(
            data_dir=None, election=["ny-2026-11-03", "tx-2026-11-03"],
            public_host=None, public_port=None, private_host=None,
            private_port=None, generate_limit=None, generate_window=None,
            trust_forwarded_for=None, heartbeat_timeout=None,
            eta_default_minutes=None, max_upload_mb=None, geocoder_url=None)
        self.assertEqual(load_config(ns).election,
                         "ny-2026-11-03,tx-2026-11-03")

    def test_two_elections_one_state_is_an_error(self):
        _write_election(self.root, "ny-2026-06-23", "ny", [
            ("prop-1", "", "Proposal 1: Another")])
        with self.assertRaises(ElectionResolutionError) as cm:
            build_deps(_make_config(self.data_dir, election=None),
                       warn=lambda m: None)
        self.assertIn("ny-2026-06-23", str(cm.exception))
        self.assertIn("ny-2026-11-03", str(cm.exception))


class ZipRoutingTest(MultiStateTestCase):
    def test_zip_in_one_state(self):
        status, body = self.get("/api/zip/10001")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "ny")
        self.assertEqual(body["election"], "ny-2026-11-03")
        self.assertEqual(body["kinds"]["sldl"][0]["name"],
                         "State Assembly District 1")
        self.assertEqual(body["chambers"],
                         {"sldu": "State Senate", "sldl": "State Assembly"})

        status, body = self.get("/api/zip/99901")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "ca")
        self.assertEqual(body["election"], "ca-2026-11-03")

    def test_straddling_zip_asks_for_address(self):
        status, body = self.get("/api/zip/99902")
        self.assertEqual(status, 200)
        self.assertTrue(body["needs_address"])
        self.assertEqual(sorted(s["state"] for s in body["states"]),
                         ["ca", "ny"])
        status, _ = self.get("/api/zip/99902/shapes")
        self.assertEqual(status, 409)

    def test_uncovered_zip(self):
        cases = {
            "33101": "We don't cover Florida yet",
            "97201": "We don't cover Oregon yet",
            "00000": "We don't cover this zip yet",
        }
        for zip_code, message in cases.items():
            with self.subTest(zip_code):
                status, body = self.get(f"/api/zip/{zip_code}")
                self.assertEqual(status, 404)
                self.assertEqual(body["error"], message)
                self.assertFalse(body["covered"])

    def test_served_state_zip_without_data(self):
        # A New York prefix the fake New York has no data for, and a
        # Texas one (Texas is served, without geo data): the address
        # lookup can still find these, so not "we don't cover".
        for zip_code in ("12345", "75201"):
            with self.subTest(zip_code):
                status, body = self.get(f"/api/zip/{zip_code}")
                self.assertEqual(status, 404)
                self.assertTrue(body["covered"])
                self.assertEqual(body["error"],
                                 "no district data for this zip")


class BallotRoutingTest(MultiStateTestCase):
    def _ballot_ids(self, *divisions):
        query = "&".join(f"d={d}" for d in divisions)
        status, body = self.get(f"/api/ballot?{query}")
        self.assertEqual(status, 200)
        return body, [c["id"] for lvl in body["levels"]
                      for c in lvl["contests"]]

    def test_ballot_by_state(self):
        body, ids = self._ballot_ids("ocd-division/country:us/state:ny",
                                     "ocd-division/country:us/state:ny/sldl:1")
        self.assertEqual(body["election"], "ny-2026-11-03")
        self.assertEqual(ids, ["ny-2026-11-03-prop-1",
                               "ny-2026-11-03-sldl-1"])
        self.assertEqual(body["chambers"]["sldl"], "State Assembly")

        body, ids = self._ballot_ids("ocd-division/country:us/state:ca",
                                     "ocd-division/country:us/state:ca/cd:1")
        self.assertEqual(body["election"], "ca-2026-11-03")
        self.assertEqual(ids, ["ca-2026-11-03-prop-1", "ca-2026-11-03-cd-1"])

        # Texas has no geo data but its ballot still serves.
        body, ids = self._ballot_ids("ocd-division/country:us/state:tx")
        self.assertEqual(ids, ["tx-2026-11-03-prop-1"])
        self.assertEqual(body["chambers"]["sldl"], "State House")

    def test_ballot_without_a_served_state(self):
        status, _ = self.get("/api/ballot?d=ocd-division/country:us/state:fl")
        self.assertEqual(status, 404)

    def test_contest_and_generate_in_any_state(self):
        status, body = self.get("/api/contest/ny-2026-11-03-prop-1")
        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "Proposal 1: Fake New York Measure")
        status, body, _ = self._public(
            "POST", "/api/generate", {"contest": "tx-2026-11-03-prop-1"})
        self.assertIn(status, (200, 201))
        job = self.deps.queue.get_job(body["job"]["id"])
        self.assertEqual(job["election"], "tx-2026-11-03")
        self.assertEqual(job["division"], "ocd-division/country:us/state:tx")


class AddressRoutingTest(MultiStateTestCase):
    def _address(self, doc):
        self.deps.geocoder_fetch = lambda url: doc
        return self._public("POST", "/api/address", {"address": "1 Fake St"})

    def test_address_routes_to_its_state(self):
        status, body, _ = self._address(_geocoder_doc("36"))
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "ny")
        self.assertEqual(body["election"], "ny-2026-11-03")
        self.assertIn({"ocd_id": "ocd-division/country:us/state:ny",
                       "name": "Statewide"}, body["kinds"]["state"])
        self.assertEqual(body["kinds"]["cd"][0]["ocd_id"],
                         "ocd-division/country:us/state:ny/cd:1")
        # Missing legislative layers come from New York's own shapes.
        self.assertEqual(body["kinds"]["sldl"][0]["name"],
                         "State Assembly District 1")

        # And the address's divisions give New York's ballot.
        query = "&".join(f"d={e['ocd_id']}" for entries in
                         body["kinds"].values() for e in entries)
        status, ballot = self.get(f"/api/ballot?{query}")
        self.assertEqual(ballot["election"], "ny-2026-11-03")

        status, body, _ = self._address(_geocoder_doc("06"))
        self.assertEqual(body["state"], "ca")

    def test_address_in_uncovered_state(self):
        status, body, _ = self._address(_geocoder_doc("12"))
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "We don't cover Florida yet")
        self.assertFalse(body["covered"])


class ChamberLabelTest(unittest.TestCase):
    def test_lower_house_label_follows_state(self):
        cases = {"ca": "State Assembly", "ny": "State Assembly",
                 "ut": "State House", "or": "State House",
                 "id": "State House", "wa": "State House",
                 "az": "State House", "oh": "State House",
                 "tx": "State House", "fl": "State House"}
        for state, chamber in cases.items():
            with self.subTest(state):
                self.assertEqual(ocd_id("sldl", "99001", state)[1],
                                 f"{chamber} District 1")
                self.assertEqual(ocd_id("sldu", "99001", state)[1],
                                 "State Senate District 1")

    def test_dc_has_no_legislature(self):
        self.assertIsNone(ocd_id("sldu", "11001", "dc"))
        self.assertIsNone(ocd_id("sldl", "11001", "dc"))

    def test_at_large_and_delegate_districts(self):
        self.assertEqual(ocd_id("cd", "5600", "wy")[1],
                         "At-large Congressional District")
        self.assertEqual(ocd_id("cd", "1198", "dc")[1],
                         "Delegate District (at large)")
        self.assertEqual(ocd_id("cd", "0612", "ca")[1],
                         "Congressional District 12")


class CliWarningTest(unittest.TestCase):
    def test_cli_warns_for_missing_geo(self):
        import os
        from ballotreels.cli import main
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        _write_election(tmp / "data", "oh-2026-11-03", "oh", [])
        old_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = tmp / "data"
        self.addCleanup(setattr, site_config, "DATA_ROOT", old_root)
        # A bad port makes serve stop right after loading, before it
        # would block serving.
        old = os.environ.get("BALLOTREELS_TOKEN")
        os.environ["BALLOTREELS_TOKEN"] = "t"
        err = io.StringIO()
        try:
            with self.assertRaises(OverflowError):
                main(["serve", "--data-dir", str(tmp / "var"),
                      "--public-port", "70000", "--private-port", "0"],
                     out=io.StringIO(), err=err)
        finally:
            if old is None:
                os.environ.pop("BALLOTREELS_TOKEN", None)
            else:
                os.environ["BALLOTREELS_TOKEN"] = old
        self.assertIn("no geo data for 'oh'", err.getvalue())


if __name__ == "__main__":
    unittest.main()


class DcGeoBuildTest(unittest.TestCase):
    """`geo build --state dc` from fixtures shaped like TIGER's: D.C. has
    no SLDU/SLDL files, a county-equivalent named "District of
    Columbia", and the delegate's district, code 98."""

    def setUp(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.data_dir = tmp / "var"
        self.warnings = geo_fixtures.build_simple_state_geo(
            self.data_dir, "dc", ["20001", "20002"], cd_code="98",
            county_name="District of Columbia",
            county_namelsad="District of Columbia")
        self.geo_dir = self.data_dir / "geo" / "dc"

    def test_no_legislature_downloads_or_files(self):
        from ballotreels.geo.build import census_urls
        self.assertEqual(self.warnings, [])
        self.assertFalse(any(n.startswith("sld") for n in census_urls("dc")))
        self.assertFalse((self.geo_dir / "sldu.geojson").exists())
        self.assertFalse((self.geo_dir / "sldl.geojson").exists())

    def test_labels(self):
        from ballotreels.geo.lookup import GeoData
        result = GeoData.load(self.geo_dir).zip_districts("20001")
        self.assertEqual(sorted(result["kinds"]),
                         ["cd", "county", "state"])
        self.assertEqual(result["kinds"]["county"][0]["name"],
                         "District of Columbia")
        self.assertEqual(result["kinds"]["cd"][0]["name"],
                         "Delegate District (at large)")
        self.assertEqual(result["chambers"], {})

    def test_county_display_uses_namelsad(self):
        # Elsewhere NAMELSAD carries the "County" (or "Parish", ...).
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        geo_fixtures.build_simple_state_geo(
            tmp, "la", ["70112"], county_name="Orleans",
            county_namelsad="Orleans Parish")
        from ballotreels.geo.lookup import GeoData
        result = GeoData.load(tmp / "geo" / "la").zip_districts("70112")
        self.assertEqual(result["kinds"]["county"][0]["name"],
                         "Orleans Parish")
        self.assertEqual(result["kinds"]["county"][0]["ocd_id"],
                         "ocd-division/country:us/state:la/county:orleans")

    def test_dc_address_has_no_legislative_districts(self):
        from ballotreels.geo.geocoder import lookup_address
        from ballotreels.geo.lookup import GeoData
        doc = json.dumps({"result": {"addressMatches": [{
            "matchedAddress": "1 FAKE ST NW, WASHINGTON, DC",
            "coordinates": {"x": 1.2, "y": 1.2},
            "geographies": {
                "States": [{"GEOID": "11"}],
                "119th Congressional Districts": [{"GEOID": "1198"}],
                "Counties": [{"GEOID": "11001",
                              "NAME": "District of Columbia",
                              "BASENAME": "District of Columbia"}]}}]}})
        result = lookup_address("1 Fake St NW", lambda url: doc,
                                "https://geocoder.example.test",
                                {"dc": GeoData.load(self.geo_dir)})
        self.assertEqual(sorted(result["kinds"]), ["cd", "county", "state"])
        self.assertEqual(result["kinds"]["county"][0]["name"],
                         "District of Columbia")
        self.assertEqual(result["kinds"]["cd"][0]["name"],
                         "Delegate District (at large)")


class SiteLabelsTest(unittest.TestCase):
    def test_app_js_takes_chambers_from_the_answer(self):
        from .helpers import REPO
        app_js = (REPO / "ballotreels" / "site" / "static" /
                  "app.js").read_text(encoding="utf-8")
        self.assertNotIn('"State Assembly"', app_js)
        self.assertNotIn('"State Senate district"', app_js)
        for needle in ("body.chambers", "zipDoc.chambers", "needs_address",
                       "covered === false"):
            self.assertIn(needle, app_js)
