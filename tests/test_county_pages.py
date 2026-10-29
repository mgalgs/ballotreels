"""County pages (/<st>/<year>/county/<county>): which cities and school
districts each county holds (ballotreels.geo.counties, from the built
shapes), and the pages themselves, over the fake counties of
tests/fixtures/counties/ (see its contests.toml)."""

import io
import json
import re
import shutil
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import ballotreels.site.config as site_config
from ballotreels.cli import main as cli_main
from ballotreels.geo.counties import FILENAME, county_doc, write_counties
from ballotreels.index import ballot_order, load_index
from ballotreels.site import pages, server
from ballotreels.site.server import build_deps, make_servers

from . import geo_fixtures
from .helpers import REPO
from .test_serve_public import ServerTestCase, _make_config

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

    def test_slivers_both_ways_along_a_bending_line_do_not_count(self):
        # Kink lies in A but for a 0.0008-degree overshoot past A's
        # north line and its east line, both into B, an L around A.
        def fc(*features):
            return {"type": "FeatureCollection", "features": [
                {"type": "Feature",
                 "properties": {"ocd_id": f"{STATE}/{i}", "name": i},
                 "geometry": {"type": "Polygon", "coordinates": [ring]}}
                for i, ring in features]}
        a = [[-120, 38], [-119.5, 38], [-119.5, 38.5], [-120, 38.5],
             [-120, 38]]
        b = [[-120, 38.5], [-120, 39], [-119, 39], [-119, 38],
             [-119.5, 38], [-119.5, 38.5], [-120, 38.5]]
        kink = [[-119.8, 38.2], [-119.4992, 38.2], [-119.4992, 38.5008],
                [-119.8, 38.5008], [-119.8, 38.2]]
        with tempfile.TemporaryDirectory() as tmp:
            geo = Path(tmp)
            for kind, doc in (("county", fc(("county:a", a),
                                            ("county:b", b))),
                              ("place", fc(("place:kink", kink)))):
                (geo / f"{kind}.geojson").write_text(json.dumps(doc),
                                                     encoding="utf-8")
            self.assertEqual(_counties_of(county_doc(geo),
                                          f"{STATE}/place:kink"),
                             [f"{STATE}/county:a"])

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


def _ids(doc):
    return {lvl["level"]: [c["id"].removeprefix("ca-2026-11-03-")
                           for c in lvl["contests"]]
            for lvl in doc["levels"]}


class CountyServerTestCase(ServerTestCase):
    """The public listener over tests/fixtures/counties/: its election,
    and its shapes with counties.json written from them (unless
    `with_counties` is False: a build from before the step)."""

    with_counties = True

    def setUp(self):
        self._old_data_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = FIXTURE
        self.addCleanup(self._restore_data_root)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name) / "var"
        geo = self.data_dir / "geo" / "ca"
        shutil.copytree(FIXTURE_GEO, geo)
        if self.with_counties:
            write_counties(geo)
        self.warnings = []
        self.config = _make_config(self.data_dir)
        self.deps = build_deps(self.config, warn=self.warnings.append)
        self.public, self.private = make_servers(self.deps)
        self.addCleanup(self.deps.queue.close)
        for srv in (self.public, self.private):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(self._shutdown)

    def get_json(self, path, status=200):
        resp, body = self.get(self.public_port, path)
        self.assertEqual(resp.status, status, body)
        return json.loads(body)

    def county(self, slug):
        return self.get_json(f"/api/county/ca/2026/{slug}")

    def page(self, path, status=200):
        resp, body = self.get(self.public_port, path)
        self.assertEqual(resp.status, status, body)
        return body.decode("utf-8")


class CountyPageTest(CountyServerTestCase):
    def test_a_countywide_measure_is_on_its_county_only(self):
        self.assertEqual(_ids(self.county("alpha"))["county"],
                         ["alpha-county-measure-a"])
        for slug in ("beta", "gamma", "delta"):
            with self.subTest(slug):
                ids = [i for ids in _ids(self.county(slug)).values()
                       for i in ids]
                self.assertNotIn("alpha-county-measure-a", ids)

    def test_measures_by_level(self):
        self.assertEqual(_ids(self.county("alpha")), {
            "county": ["alpha-county-measure-a"],
            "place": ["alphaville-measure-c", "northedge-measure-n"],
            "school_district": ["twin-valley-measure-t"]})
        self.assertEqual(_ids(self.county("beta")), {
            "county": ["beta-county-measure-b"],
            "place": ["edgetown-measure-e", "sliverton-measure-s"],
            "school_district": ["twin-valley-measure-t"],
            "special": ["beta-fire-measure-f"]})
        self.assertEqual([lvl["level"] for lvl in self.county("beta")
                          ["levels"]],
                         ["county", "place", "school_district", "special"])

    def test_a_district_touching_the_county_line_is_not_listed(self):
        # Edgetown's edge is Gamma's line; Sliverton crosses it by a
        # sliver.
        self.assertEqual(_ids(self.county("gamma")),
                         {"school_district": ["gamma-elementary-measure-g"]})

    def test_statewide_measures_are_not_listed(self):
        doc = self.county("alpha")
        ids = [i for ids in _ids(doc).values() for i in ids]
        self.assertNotIn("prop-1", ids)
        self.assertEqual(doc["state_path"], "/ca")

    def test_each_measure_links_to_its_page(self):
        contest = self.county("alpha")["levels"][0]["contests"][0]
        self.assertEqual(contest["path"], "/ca/2026/alpha-county-measure-a")
        self.assertEqual(contest["title"],
                         "Measure A: Fake Alpha County Sales Tax")
        self.page(contest["path"])

    def test_heading_and_head_tags(self):
        doc = self.county("alpha")
        self.assertEqual(doc["heading"],
                         "Alpha County ballot measures, November 3, 2026")
        self.assertEqual(doc["page_title"], doc["heading"])
        html = self.page("/ca/2026/county/alpha")
        self.assertIn("<title>Alpha County ballot measures, November 3, "
                      "2026</title>", html)
        self.assertIn('<link rel="canonical" href="https://ballotreels.org'
                      '/ca/2026/county/alpha">', html)
        self.assertIn("4 measures on the ballot in Alpha County, "
                      "California", html)

    def test_a_county_with_no_measures_says_so(self):
        doc = self.county("delta")
        self.assertEqual(doc["levels"], [])
        self.assertEqual(doc["none_text"],
                         "No local measures are on the ballot in Delta "
                         "County.")
        html = self.page("/ca/2026/county/delta")
        self.assertIn('content="No local measures are on the ballot in '
                      'Delta County.', html)

    def test_unknown_county_or_year_is_not_found(self):
        for path in ("/ca/2026/county/nowhere", "/ca/2024/county/alpha",
                     "/ut/2026/county/alpha", "/ca/2026/county",
                     "/ca/2026/county/alpha/more"):
            with self.subTest(path):
                self.page(path, status=404)
        self.get_json("/api/county/ca/2026/nowhere", status=404)
        self.get_json("/api/county/ca/2024/alpha", status=404)

    def test_typed_path_is_redirected(self):
        resp, _ = self.get(self.public_port, "/CA/2026/County/Alpha/")
        self.assertEqual(resp.status, 301)
        self.assertEqual(resp.getheader("Location"),
                         "/ca/2026/county/alpha")

    def test_state_page_lists_the_counties(self):
        doc = self.get_json("/api/state/ca")
        self.assertEqual(doc["counties"], [
            {"name": f"{n} County", "path": f"/ca/2026/county/{n.lower()}"}
            for n in ("Alpha", "Beta", "Delta", "Gamma")])
        # the statewide measures as before
        self.assertEqual([c["id"] for lvl in doc["levels"]
                          for c in lvl["contests"]], ["ca-2026-11-03-prop-1"])

    def test_measure_page_links_its_counties(self):
        def counties(slug):
            return self.get_json(f"/api/contest/ca/2026/{slug}")["counties"]
        self.assertEqual(counties("twin-valley-measure-t"), [
            {"name": "Alpha County", "path": "/ca/2026/county/alpha"},
            {"name": "Beta County", "path": "/ca/2026/county/beta"}])
        self.assertEqual(counties("beta-fire-measure-f"),
                         [{"name": "Beta County",
                           "path": "/ca/2026/county/beta"}])
        self.assertEqual(counties("prop-1"), [])

    def test_sitemap(self):
        resp, body = self.get(self.public_port, "/sitemap.xml")
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        base = "https://ballotreels.org"
        locs = [e.text.removeprefix(base)
                for e in ET.fromstring(body).iter(f"{ns}loc")]
        county_pages = [l for l in locs if "/county/" in l]
        self.assertEqual(county_pages, [f"/ca/2026/county/{n}" for n in
                                        ("alpha", "beta", "delta", "gamma")])
        # everything else as it was: home, the state, its measures
        index = load_index(FIXTURE / "ca-2026-11-03")
        self.assertEqual(
            [l for l in locs if "/county/" not in l],
            ["/", "/ca"] + [pages.contest_path("ca", "ca-2026-11-03", e.id)
                            for e in ballot_order(index)])
        for path in county_pages:
            self.page(path)

    def test_app_routes_county_pages(self):
        app = (REPO / "ballotreels" / "site" / "static" /
               "app.js").read_text(encoding="utf-8")
        self.assertIn("renderCounty(`/api/county/", app)


class HeroTest(CountyServerTestCase):
    def test_state_hero_without_a_flag_falls_back_to_a_tone(self):
        hero = self.get_json("/api/state/ca")["hero"]
        self.assertTrue(hero.startswith('<svg class="hero-map"'))
        self.assertIn('aria-hidden="true"', hero)
        self.assertNotIn("<image", hero)
        self.assertIn('class="hero-tone" fill="url(#hero-tone)"', hero)
        self.assertEqual(hero.count("<path "), 4)
        self.assertNotIn("hero-county", hero)

    def test_state_hero_with_a_flag_draws_it_inside_the_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            static = Path(tmp)
            (static / "flags").mkdir()
            (static / "flags" / "ca.png").write_bytes(b"\x89PNG")
            with mock.patch.object(server, "STATIC_DIR", static):
                hero = server._hero(self.deps.states["ca"])
        self.assertRegex(hero, r'<image class="hero-flag" '
                               r'href="/static/flags/ca.png" [^>]*'
                               r'mask="url\(#hero-land\)"')

    def test_county_hero_fills_its_county(self):
        hero = self.county("beta")["hero"]
        beta_path = county_doc(FIXTURE_GEO)["hero"]["paths"][BETA]
        filled = re.findall(r'<path class="hero-county" '
                            r'data-county="([^"]+)" d="([^"]+)" '
                            r'fill="url\(#hero-hatch\)"', hero)
        self.assertEqual(filled, [(BETA, beta_path)])
        self.assertNotIn("<image", hero)
        # every county drawn, for the state's outline
        self.assertEqual(hero.count("<path "), 5)

    def test_hero_is_small(self):
        self.assertLess(len(self.county("beta")["hero"]), 4000)

    def test_hero_svg_escapes(self):
        hero = pages.hero_svg({"width": 10, "height": 10,
                               "paths": {"a": "M0 0l1 1z"}}, None,
                              '/static/flags/x.png"><script>')
        self.assertNotIn("<script>", hero)


class WithoutCountiesFileTest(CountyServerTestCase):
    with_counties = False

    def test_no_county_pages_and_a_warning(self):
        self.assertTrue(any("geo counties --state ca" in w
                            for w in self.warnings), self.warnings)
        self.page("/ca/2026/county/alpha", status=404)
        doc = self.get_json("/api/state/ca")
        self.assertEqual(doc["counties"], [])
        self.assertIsNone(doc["hero"])
        resp, body = self.get(self.public_port, "/sitemap.xml")
        self.assertNotIn(b"/county/", body)


if __name__ == "__main__":
    unittest.main()
