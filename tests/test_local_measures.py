"""Local measures (docs/ARCHITECTURE.md): county, city and school
district contests on a zip's ballot, end to end through the geo build,
the zip lookup, the ballot, the contest page and the
sitemap, over the fake San Diego of tests/geo_fixtures.py and the
fixture election in tests/fixtures/local/."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

import ballotreels.site.config as site_config
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
        division the zip answer lists, and its partial ones again as `p`
        (app.js's ballotParams)."""
        doc = self.get_json(f"/api/zip/{zip_code}")
        self.assertEqual(doc["ambiguous"], [])
        query = "&".join([f"d={e['ocd_id']}" for entries in
                          doc["kinds"].values() for e in entries] +
                         [f"p={d}" for d in doc["partial"]])
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

    def test_district_shapes_and_names(self):
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


class CountyIndexTest(unittest.TestCase):
    def test_most_local_level_first(self):
        index = load_index(ELECTION_DIR)
        self.assertEqual(level_of(SAN_DIEGO, STATE), "county")
        self.assertEqual(
            [e.id for e in ballot_order(index)],
            ["ca-2026-11-03-sd-unified-measure-f",
             "ca-2026-11-03-grossmont-measure-g",
             "ca-2026-11-03-san-diego-city-measure-d",
             "ca-2026-11-03-el-cajon-city-measure-e",
             "ca-2026-11-03-helix-water-measure-h",
             "ca-2026-11-03-sd-county-measure-a",
             "ca-2026-11-03-sd-county-measure-b",
             "ca-2026-11-03-imperial-county-measure-c",
             "ca-2026-11-03-prop-90", "ca-2026-11-03-prop-91"])
        self.assertEqual(level_of(SD_CITY, STATE), "place")
        self.assertEqual(level_of(GROSSMONT, STATE), "school_district")

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
        self.assertEqual(_ids(doc["levels"][2:3]),
                         ["ca-2026-11-03-helix-water-measure-h",
                          "ca-2026-11-03-sd-county-measure-a",
                          "ca-2026-11-03-sd-county-measure-b"])
        doc = self.ballot_for_zip("92250")
        self.assertEqual(_ids(doc["levels"][:-1]),
                         ["ca-2026-11-03-imperial-county-measure-c"])

    def test_contest_page(self):
        summary = self.ballot_for_zip("92101")["levels"][2]["contests"][1]
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


def _maybe(levels):
    return {c["id"]: c.get("maybe", False)
            for lvl in levels for c in lvl["contests"]
            if lvl["level"] in ("place", "school_district")}


class LocalBallotTest(LocalServerTestCase):
    def test_zip_wholly_in_a_city(self):
        doc = self.ballot_for_zip("92101")
        self.assertEqual([lvl["level"] for lvl in doc["levels"]],
                         ["school_district", "place", "county", "state"])
        self.assertEqual(_maybe(doc["levels"]),
                         {"ca-2026-11-03-san-diego-city-measure-d": False,
                          "ca-2026-11-03-sd-unified-measure-f": False})

    def test_zip_across_cities_lists_every_one_as_maybe(self):
        doc = self.ballot_for_zip("92102")
        self.assertEqual(_maybe(doc["levels"]),
                         {"ca-2026-11-03-san-diego-city-measure-d": True,
                          "ca-2026-11-03-el-cajon-city-measure-e": True,
                          "ca-2026-11-03-sd-unified-measure-f": True,
                          "ca-2026-11-03-grossmont-measure-g": True})

    def test_zip_partly_in_a_city(self):
        doc = self.ballot_for_zip("92103")
        self.assertEqual(_maybe(doc["levels"]),
                         {"ca-2026-11-03-el-cajon-city-measure-e": True,
                          "ca-2026-11-03-grossmont-measure-g": False})

    def test_many_divisions(self):
        # a zip's own and every city and school district it overlaps:
        # more than the ten a ballot request once allowed
        query = "&".join([f"d={STATE}/cd:{n}" for n in range(1, 12)] +
                         [f"d={GROSSMONT}"])
        doc = self.get_json(f"/api/ballot?{query}")
        self.assertIn("ca-2026-11-03-grossmont-measure-g",
                      _ids(doc["levels"]))

    def test_app_reads_the_partial_divisions(self):
        app = (REPO / "ballotreels" / "site" / "static" /
               "app.js").read_text(encoding="utf-8")
        self.assertIn('params.getAll("p")', app)
        self.assertIn("ballotParams(body.kinds, body.partial)", app)
        self.assertIn("depending on your address", app)


class VotersRuleTest(unittest.TestCase):
    def problem(self, slug, voters=None, division=SAN_DIEGO, kind="measure"):
        from ballotreels.index import voters_problem
        return voters_problem(kind, division, slug, voters)

    def test_the_county_s_own_measure_needs_none(self):
        self.assertIsNone(self.problem("sd-county-measure-a"))
        self.assertIsNone(self.problem("san-diego-county-measure-b"))

    def test_a_special_district_s_measure_needs_one(self):
        self.assertIn("'voters'", self.problem("helix-water-measure-c"))
        self.assertIn("'voters'",
                      self.problem("orange-county-water-measure-x"))
        self.assertIsNone(self.problem("helix-water-measure-c",
                                       "the Helix Water District"))

    def test_only_under_a_county(self):
        self.assertIsNone(self.problem("san-diego-city-measure-d",
                                       division=SD_CITY))
        self.assertIn("not a county", self.problem(
            "san-diego-city-measure-d", "the City of San Diego",
            division=SD_CITY))
        self.assertIsNone(self.problem("supervisor-3", kind="race"))

    def test_said_inside_a_sentence(self):
        self.assertIn("period", self.problem(
            "helix-water-measure-c", "the Helix Water District."))
        self.assertIn("non-empty", self.problem("helix-water-measure-c", ""))

    def test_the_index_refuses_a_measure_without_one(self):
        import shutil
        from ballotreels.index import ContestIndexError
        with tempfile.TemporaryDirectory() as tmp:
            election = Path(tmp) / "ca-2026-11-03"
            shutil.copytree(ELECTION_DIR, election)
            sources = election / "helix-water-measure-h" / "sources.toml"
            sources.write_text(sources.read_text().replace(
                'voters = "the Helix Water District"\n', ""))
            with self.assertRaises(ContestIndexError) as cm:
                load_index(election)
            self.assertIn("helix-water-measure-h", str(cm.exception))
        self.assertEqual(
            load_index(ELECTION_DIR).get(
                "ca-2026-11-03-helix-water-measure-h").voters,
            "the Helix Water District")


class VotersCheckTest(unittest.TestCase):
    """The check, and the film's card, on a copy of the frozen Prop 2
    given a card (as tests/test_card.py's) and moved under a county."""

    def setUp(self):
        import shutil

        from .helpers import PROP_2
        from .test_card import CARD, VERSION
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "helix-water-measure-c"
        shutil.copytree(PROP_2, self.dir)
        self.script = self.dir / "script.toml"
        text = self.script.read_text(encoding="utf-8")
        self.assertEqual(text.count(VERSION), 1)
        self.script.write_text(text.replace(VERSION, VERSION + CARD),
                               encoding="utf-8")
        self.card = CARD
        self.sources = self.dir / "sources.toml"
        text = self.sources.read_text(encoding="utf-8")
        for old, new in (
                ('id = "ca-2026-11-03-prop-2"',
                 'id = "ca-2026-11-03-helix-water-measure-c"'),
                (f'division = "{STATE}"', f'division = "{SAN_DIEGO}"')):
            self.assertEqual(text.count(old), 1, old)
            text = text.replace(old, new)
        self.sources.write_text(text, encoding="utf-8")

    def failures(self):
        from ballotreels import load_contest
        from ballotreels.checks import check_voters
        return [str(f) for f in check_voters(load_contest(self.dir))]

    def set_voters(self, voters):
        text = self.sources.read_text(encoding="utf-8")
        self.sources.write_text(text.replace(
            f'division = "{SAN_DIEGO}"\n',
            f'division = "{SAN_DIEGO}"\nvoters = "{voters}"\n'),
            encoding="utf-8")

    def test_missing(self):
        self.assertEqual(len(self.failures()), 1)
        self.assertIn("[voters]", self.failures()[0])

    def test_present(self):
        self.set_voters("the Helix Water District")
        self.assertEqual(self.failures(), [])

    def test_needs_a_card(self):
        self.set_voters("the Helix Water District")
        text = self.script.read_text(encoding="utf-8")
        self.script.write_text(text.replace(self.card, ""), encoding="utf-8")
        self.assertEqual(len(self.failures()), 1)
        self.assertIn("no [card]", self.failures()[0])

    def test_film_card_says_who_votes(self):
        from .choice_fixture import load_film
        self.set_voters("the Helix Water District")
        # Prop 2's own id again: the id picks which side plays first
        # (STANDARD.md rule 2.4), and its narration is in Prop 2's order.
        text = self.sources.read_text(encoding="utf-8")
        self.sources.write_text(text.replace(
            "helix-water-measure-c", "prop-2"), encoding="utf-8")
        film = load_film(self.dir)
        line = "Only voters in the Helix Water District vote on this."
        self.assertEqual(film.VOTERS, line)
        for fmt, L in film.LAYOUTS.items():
            paper_box, parts = film.page_plan(fmt)
            note, (x, y, w) = parts["voters"]
            self.assertEqual(" ".join(r[0] for r in note.runs), line)
            title = next(f for f in parts["flows"] if f.field == "title")
            self.assertGreater(title.y, y, fmt)
            self.assertLessEqual(note.y + note.height, y, fmt)
            _, marks = film.page_static(paper_box, parts, L)
            self.assertEqual(marks[0][1], line, fmt)
            # still on the paper
            self.assertLessEqual(max(f.y + f.height for f in parts["flows"]),
                                 paper_box.bottom, fmt)


class VotersOnTheSiteTest(LocalServerTestCase):
    LINE = "Only voters in the Helix Water District vote on this."

    def test_ballot_and_contest_page(self):
        doc = self.ballot_for_zip("92101")
        county = next(lvl for lvl in doc["levels"]
                      if lvl["level"] == "county")
        voters = {c["id"]: c.get("voters") for c in county["contests"]}
        self.assertEqual(voters, {
            "ca-2026-11-03-sd-county-measure-a": None,
            "ca-2026-11-03-sd-county-measure-b": None,
            "ca-2026-11-03-helix-water-measure-h": self.LINE})
        doc = self.get_json("/api/contest/ca/2026/helix-water-measure-h")
        self.assertEqual(doc["voters"], self.LINE)
        doc = self.get_json("/api/contest/ca/2026/sd-county-measure-a")
        self.assertNotIn("voters", doc)

    def test_app_shows_it(self):
        app = (REPO / "ballotreels" / "site" / "static" /
               "app.js").read_text(encoding="utf-8")
        self.assertIn("contest.voters", app)


class JurisdictionOnTheSiteTest(LocalServerTestCase):
    """A local contest names whose it is, on the ballot, its page and its
    tags, so a zip across two cities says which measure is which."""

    def test_ballot_names_each_city_and_district(self):
        doc = self.ballot_for_zip("92102")
        names = {c["id"]: c.get("jurisdiction")
                 for lvl in doc["levels"] for c in lvl["contests"]}
        self.assertEqual(names["ca-2026-11-03-prop-90"], None)
        self.assertEqual(names["ca-2026-11-03-sd-county-measure-a"],
                         "San Diego County")
        self.assertEqual(names["ca-2026-11-03-san-diego-city-measure-d"],
                         "City of San Diego")
        self.assertEqual(names["ca-2026-11-03-el-cajon-city-measure-e"],
                         "City of El Cajon")
        self.assertEqual(names["ca-2026-11-03-grossmont-measure-g"],
                         "Grossmont Union High School District")

    def test_contest_page_and_tags(self):
        for path, where in (
                ("sd-county-measure-a", "San Diego County"),
                ("san-diego-city-measure-d", "City of San Diego"),
                ("helix-water-measure-h", "Helix Water District")):
            doc = self.get_json(f"/api/contest/ca/2026/{path}")
            self.assertTrue(doc["page_title"].startswith(f"{where} Measure"),
                            doc["page_title"])
            resp, body = self.get(self.public_port, f"/ca/2026/{path}")
            self.assertEqual(resp.status, 200)
            self.assertIn(f"<title>{where} Measure".encode(), body)
            self.assertNotIn(b"California Measure", body)
        doc = self.get_json("/api/contest/ca/2026/prop-90")
        self.assertNotIn("jurisdiction", doc)
        self.assertTrue(doc["page_title"].startswith("California Prop"))

    def test_app_shows_it(self):
        app = (REPO / "ballotreels" / "site" / "static" /
               "app.js").read_text(encoding="utf-8")
        self.assertIn("contest.jurisdiction", app)
        self.assertIn("...localNotes(body)", app)
