"""Local measures (docs/ARCHITECTURE.md): county contests on a zip's
ballot, end to end through the zip lookup, the ballot, the contest page
and the sitemap, over the fake San Diego of tests/geo_fixtures.py and
the fixture election in tests/fixtures/local/."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

import ballotreels.site.config as site_config
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
