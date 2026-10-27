"""Browsing by state, states with nothing on the ballot, and contests
whose video failed or was cancelled (fake fixtures, apart from the
check on the real empty elections under data/)."""

import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

import ballotreels.site.config as site_config
from ballotreels.index import load_index
from ballotreels.site.server import build_deps, make_servers

from . import geo_fixtures
from .helpers import REPO
from .test_multistate import _write_election
from .test_serve_private import PrivateApiMixin
from .test_serve_public import _make_config

STATIC_DIR = REPO / "ballotreels" / "site" / "static"

CA_PROP_1 = "ca-2026-11-03-prop-1"
CA_PROP_2 = "ca-2026-11-03-prop-2"


class BrowseTestCase(PrivateApiMixin, unittest.TestCase):
    def setUp(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = tmp / "data"
        _write_election(self.root, "ca-2026-11-03", "ca", [
            ("prop-1", "", "Proposition 1: Fake California Measure"),
            ("cd-1", "/cd:1", "Fake California District Measure"),
            ("prop-2", "", "Proposition 2: Another Fake Measure")])
        _write_election(self.root, "ut-2026-11-03", "ut", [
            ("amendment-a", "", "Constitutional Amendment A: Fake")])
        # Nothing on the ballot: New York with geo data, Texas without.
        _write_election(self.root, "ny-2026-11-03", "ny", [])
        _write_election(self.root, "tx-2026-11-03", "tx", [])
        old_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = self.root
        self.addCleanup(setattr, site_config, "DATA_ROOT", old_root)

        self.data_dir = tmp / "var"
        geo_fixtures.build_fixture_geo(self.data_dir)
        geo_fixtures.build_simple_state_geo(self.data_dir, "ny", ["10001"])
        self.deps = build_deps(
            _make_config(self.data_dir, election=None,
                         require_approval=False), warn=lambda m: None)
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

    def ballot(self, zip_doc):
        query = "&".join(f"d={e['ocd_id']}" for entries in
                         zip_doc["kinds"].values() for e in entries)
        status, body = self.get(f"/api/ballot?{query}")
        self.assertEqual(status, 200)
        return body


class StateListTest(BrowseTestCase):
    def test_lists_served_states_by_name(self):
        status, body = self.get("/api/states")
        self.assertEqual(status, 200)
        self.assertEqual(
            [(s["state"], s["name"], s["election"]) for s in body["states"]],
            [("ca", "California", "ca-2026-11-03"),
             ("ny", "New York", "ny-2026-11-03"),
             ("tx", "Texas", "tx-2026-11-03"),
             ("ut", "Utah", "ut-2026-11-03")])


class StatePageTest(BrowseTestCase):
    def test_statewide_measures_only(self):
        status, body = self.get("/api/state/ca")
        self.assertEqual(status, 200)
        self.assertEqual(body["state_name"], "California")
        self.assertEqual(body["election"], "ca-2026-11-03")
        self.assertFalse(body["empty_election"])
        self.assertEqual([lvl["level"] for lvl in body["levels"]], ["state"])
        contests = body["levels"][0]["contests"]
        # The district measure is not statewide: only a ballot shows it.
        self.assertEqual([c["id"] for c in contests], [CA_PROP_1, CA_PROP_2])
        self.assertEqual({c["status"] for c in contests}, {"none"})

    def test_video_status_as_on_the_ballot(self):
        status, body, _ = self._public("POST", "/api/generate",
                                       {"contest": CA_PROP_1})
        self.assertEqual(status, 201)
        _, state = self.get("/api/state/ca")
        _, ballot = self.get(
            "/api/ballot?d=ocd-division/country:us/state:ca")
        from_state = {c["id"]: c for c in state["levels"][0]["contests"]}
        from_ballot = {c["id"]: c for c in ballot["levels"][0]["contests"]}
        self.assertEqual(from_state, from_ballot)
        self.assertEqual(from_state[CA_PROP_1]["status"], "queued")

    def test_empty_state(self):
        status, body = self.get("/api/state/tx")
        self.assertEqual(status, 200)
        self.assertEqual(body["state_name"], "Texas")
        self.assertTrue(body["empty_election"])
        self.assertEqual(body["levels"], [])

    def test_unserved_state(self):
        status, body = self.get("/api/state/fl")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "We don't cover Florida yet")
        self.assertFalse(body["covered"])
        status, _ = self.get("/api/state/CA")
        self.assertEqual(status, 404)

    def test_state_url_serves_the_page(self):
        for path in ("/state/ca", "/state/tx", "/state/fl"):
            with self.subTest(path):
                status, raw, headers = self._public_raw(path)
                self.assertEqual(status, 200)
                self.assertIn(b"/static/app.js", raw)
        for path in ("/state/california", "/state/ca/x", "/states"):
            with self.subTest(path):
                status, _, _ = self._public_raw(path)
                self.assertEqual(status, 404)

    def _public_raw(self, path):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.public_port,
                                          timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body, resp.headers


class EmptyElectionZipTest(BrowseTestCase):
    def test_zip_without_geo_gets_an_empty_ballot(self):
        status, body = self.get("/api/zip/75201")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "tx")
        self.assertEqual(body["election"], "tx-2026-11-03")
        self.assertEqual(body["ambiguous"], [])
        ballot = self.ballot(body)
        self.assertEqual(ballot["election"], "tx-2026-11-03")
        self.assertEqual(ballot["state_name"], "Texas")
        self.assertTrue(ballot["empty_election"])
        self.assertEqual(ballot["levels"], [])

    def test_zip_with_geo_gets_an_empty_ballot(self):
        status, body = self.get("/api/zip/10001")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "ny")
        ballot = self.ballot(body)
        self.assertEqual(ballot["state_name"], "New York")
        self.assertTrue(ballot["empty_election"])
        self.assertEqual(ballot["levels"], [])
        # A New York zip the fake geo data lacks: still New York's ballot.
        status, body = self.get("/api/zip/12345")
        self.assertEqual(status, 200)
        self.assertEqual(body["election"], "ny-2026-11-03")

    def test_unserved_state_still_not_covered(self):
        status, body = self.get("/api/zip/33101")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "We don't cover Florida yet")
        self.assertFalse(body["covered"])

    def test_served_state_ballot_unchanged(self):
        status, body = self.get("/api/zip/99901")
        self.assertEqual(status, 200)
        self.assertEqual(body["election"], "ca-2026-11-03")
        ballot = self.ballot(body)
        self.assertFalse(ballot["empty_election"])
        self.assertIn(CA_PROP_1, [c["id"] for lvl in ballot["levels"]
                                  for c in lvl["contests"]])
        # A served state with contests but no data for the zip.
        status, body = self.get("/api/zip/84101")
        self.assertEqual(status, 404)
        self.assertTrue(body["covered"])


class FailedOrCancelledStatusTest(BrowseTestCase):
    def _job_for(self, contest):
        status, body, _ = self._public("POST", "/api/generate",
                                       {"contest": contest})
        self.assertEqual(status, 201)
        return body["job"]["id"]

    def test_status_on_load(self):
        failed = self._job_for(CA_PROP_1)
        claim = self.deps.queue.claim("w1")["claim"]
        self.deps.queue.fail(failed, claim, "script", "no script")
        cancelled = self._job_for(CA_PROP_2)
        self.deps.queue.transition(cancelled, "cancel")
        expected = {CA_PROP_1: "failed", CA_PROP_2: "cancelled"}
        for contest, state in expected.items():
            with self.subTest(contest):
                status, body = self.get(f"/api/contest/{contest}")
                self.assertEqual(status, 200)
                self.assertEqual(body["status"], state)
                self.assertIsNone(body["job"])
        _, body = self.get("/api/state/ca")
        self.assertEqual({c["id"]: c["status"]
                          for c in body["levels"][0]["contests"]}, expected)

        # The operator's retry makes it live again.
        status, _, _ = self._private("POST",
                                     f"/admin/api/jobs/{failed}/retry")
        self.assertEqual(status, 200)
        _, body = self.get(f"/api/contest/{CA_PROP_1}")
        self.assertEqual(body["status"], "queued")


class AppJsTest(unittest.TestCase):
    def test_app_handles_states_and_unavailable(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        for needle in ("/api/states", "/api/state/${abbr}",
                       "href: `/state/${s.state}`", "body.empty_election",
                       "There are no statewide measures on ${name}'s ballot"):
            self.assertIn(needle, app_js)
        m = re.search(r"const UNAVAILABLE_STATES = (\[[^\]]*\]);", app_js)
        self.assertIsNotNone(m)
        self.assertEqual(sorted(json.loads(m.group(1))),
                         ["cancelled", "failed", "unavailable"])


class RealEmptyElectionsTest(unittest.TestCase):
    def test_ny_or_tx_have_no_contests(self):
        for state in ("ny", "or", "tx"):
            with self.subTest(state):
                index = load_index(REPO / "data" / f"{state}-2026-11-03")
                self.assertEqual(index.election.state,
                                 f"ocd-division/country:us/state:{state}")
                self.assertEqual(index.entries, ())


if __name__ == "__main__":
    unittest.main()
