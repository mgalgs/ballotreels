import shutil
import tempfile
import unittest
from pathlib import Path

from ballotreels.adapters.ca_sos import (append_entries, build_contest_entries,
                                         fetch_measures, parse_overview)
from ballotreels.cli import _measures_ca_sos
from ballotreels.index import load_index

from .helpers import REPO

OVERVIEW_FIXTURE = (REPO / "tests" / "fixtures" / "sos" /
                    "prop-2-overview.html").read_text(encoding="utf-8")

BASE_URL = "https://voterguide.example.test"


def fake_overview(number, title, nav):
    links = "".join(
        f'<li><a href="/propositions/{n}/index.htm">Proposition {n}</a></li>'
        for n in nav)
    return (
        f'<span id="propNum">&nbsp;{number}</span>'
        f'<div class="grid-90 propName"><h2>{title}</h2></div>'
        f'<ul id="propNav">{links}</ul>')


class ParseOverviewTest(unittest.TestCase):
    def test_parse_archived_overview(self):
        number, title, nav = parse_overview(OVERVIEW_FIXTURE)
        self.assertEqual(number, "2")
        self.assertEqual(
            title,
            "INCREASES STATE’S RAINY DAY FUND. "
            "LEGISLATIVE CONSTITUTIONAL AMENDMENT.")
        self.assertEqual(nav, ("1", "2", "3", "4", "5", "37", "38", "39",
                               "40", "41", "42", "43", "44", "45"))


class FetchMeasuresTest(unittest.TestCase):
    def test_fetch_measures_walks_nav(self):
        pages = {
            "2": fake_overview("2", "FAKE MEASURE TWO.", ["2", "37"]),
            "37": fake_overview("37", "FAKE MEASURE THIRTY SEVEN.", ["2", "37"]),
        }
        calls = []

        def fetch(url):
            calls.append(url)
            n = url.split("/")[-2]
            return pages[n]

        measures = fetch_measures(fetch, BASE_URL, start_number="2")
        self.assertEqual(measures, (
            {"number": "2", "title": "FAKE MEASURE TWO."},
            {"number": "37", "title": "FAKE MEASURE THIRTY SEVEN."},
        ))
        self.assertEqual(calls, [f"{BASE_URL}/propositions/2/index.htm",
                                 f"{BASE_URL}/propositions/37/index.htm"])


class AdapterOrchestrationTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.election_dir = Path(tmp.name) / "ca-2026-11-03"
        shutil.copytree(
            REPO / "tests" / "fixtures" / "contests" / "ca-2026-11-03",
            self.election_dir)
        self.pages = {
            "90": fake_overview("90", "FAKE MEASURE NINETY.", ["90", "93"]),
            "93": fake_overview("93", "FAKE MEASURE NINETY THREE.",
                                ["90", "93"]),
        }

    def fetch(self, url):
        n = url.split("/")[-2]
        if n not in self.pages:
            raise OSError("not found")
        return self.pages[n]


class AppendsMissingMeasuresTest(AdapterOrchestrationTestCase):
    def test_appends_missing_measures(self):
        import io
        before = (self.election_dir / "contests.toml").read_text(
            encoding="utf-8")
        out = io.StringIO()
        ok = _measures_ca_sos(str(self.election_dir), BASE_URL, "90", out,
                              fetch=self.fetch)
        self.assertTrue(ok)
        after = (self.election_dir / "contests.toml").read_text(
            encoding="utf-8")
        # prop-90 already existed (untouched): its title and comments stay.
        self.assertTrue(after.startswith(before))
        self.assertIn('id = "ca-2026-11-03-prop-93"', after)
        self.assertIn('title = "Proposition 93: FAKE MEASURE NINETY THREE."',
                      after)
        self.assertEqual(after.count('id = "ca-2026-11-03-prop-90"'), 1)
        index = load_index(self.election_dir)
        self.assertIsNotNone(index.get("ca-2026-11-03-prop-93"))

    def test_idempotent(self):
        import io
        _measures_ca_sos(str(self.election_dir), BASE_URL, "90", io.StringIO(),
                         fetch=self.fetch)
        once = (self.election_dir / "contests.toml").read_text(
            encoding="utf-8")
        n = append_entries(
            self.election_dir / "contests.toml",
            build_contest_entries(
                "ca-2026-11-03", "ocd-division/country:us/state:ca",
                ({"number": "90", "title": "FAKE MEASURE NINETY."},
                 {"number": "93", "title": "FAKE MEASURE NINETY THREE."})))
        self.assertEqual(n, 0)
        twice = (self.election_dir / "contests.toml").read_text(
            encoding="utf-8")
        self.assertEqual(once, twice)


class FetchFailureTest(AdapterOrchestrationTestCase):
    def test_fetch_failure_writes_nothing(self):
        import io
        before = (self.election_dir / "contests.toml").read_text(
            encoding="utf-8")
        del self.pages["93"]
        out = io.StringIO()
        ok = _measures_ca_sos(str(self.election_dir), BASE_URL, "90", out,
                              fetch=self.fetch)
        self.assertFalse(ok)
        self.assertIn(f"{BASE_URL}/propositions/93/index.htm", out.getvalue())
        after = (self.election_dir / "contests.toml").read_text(
            encoding="utf-8")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
