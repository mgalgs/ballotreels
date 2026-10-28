import io
import shutil
import tempfile
import unittest
from pathlib import Path

from ballotreels.cli import main
from ballotreels.geo.build import (BuildError, census_urls,
                                   parse_relationship, build)
from ballotreels.geo.lookup import GeoData, ocd_id
from ballotreels.geo.shapefile import read_shapefile
from ballotreels.geo.shapes import (douglas_peucker, point_in_polygon,
                                    row_intervals, simplify_ring)

from . import geo_fixtures

STATE = "ca"


_write_source = geo_fixtures.write_fixture_source
_fetch_from = geo_fixtures.fetch_from


def _build(data_dir, state, fetch, **kwargs):
    kwargs.setdefault("urls", geo_fixtures.SLD_REL_URLS)
    return build(data_dir, state, fetch, **kwargs)


class GeoBuildTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.src_dir = self.root / "src"
        self.src_dir.mkdir()
        _write_source(self.src_dir)
        self.data_dir = self.root / "data"


class BuildWritesOnlyUnderDataDirTest(GeoBuildTestCase):
    def test_build_writes_only_under_data_dir(self):
        other = self.root / "untouched.txt"
        other.write_text("x", encoding="utf-8")
        before = other.read_bytes()
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        self.assertTrue((self.data_dir / "geo" / STATE / "zips.json").is_file())
        self.assertEqual(other.read_bytes(), before)
        # nothing written at the root besides data_dir
        self.assertEqual(
            {p.name for p in self.root.iterdir()},
            {"src", "data", "untouched.txt"})


class BuildIdempotentTest(GeoBuildTestCase):
    def test_build_idempotent(self):
        calls = []
        _build(self.data_dir, STATE, _fetch_from(self.src_dir, calls=calls))
        first = (self.data_dir / "geo" / STATE / "zips.json").read_bytes()
        calls.clear()
        _build(self.data_dir, STATE, _fetch_from(self.src_dir, calls=calls))
        second = (self.data_dir / "geo" / STATE / "zips.json").read_bytes()
        self.assertEqual(calls, [])
        self.assertEqual(first, second)


class BuildDownloadFailureTest(GeoBuildTestCase):
    def test_build_download_failure(self):
        with self.assertRaises(BuildError) as cm:
            _build(self.data_dir, STATE,
                 _fetch_from(self.src_dir, raise_for="cd.zip"))
        msg = str(cm.exception)
        self.assertIn("cd.zip", msg)
        self.assertIn(census_urls(STATE)["cd.zip"], msg)
        self.assertIn("--url", msg)
        raw_dir = self.data_dir / "geo" / ".raw" / STATE
        if raw_dir.exists():
            self.assertEqual(list(raw_dir.glob("*.part")), [])
        self.assertFalse((self.data_dir / "geo" / f"{STATE}.tmp").exists())


class BuildSwapTest(GeoBuildTestCase):
    def test_rebuild_recovers_from_stop_between_renames(self):
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        geo = self.data_dir / "geo"
        # As if an earlier build had moved the old output aside and then
        # died before moving the new one in.
        (geo / STATE).replace(geo / f"{STATE}.old")
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        self.assertTrue((geo / STATE / "zips.json").is_file())
        self.assertFalse((geo / f"{STATE}.old").exists())


class BuildCensusShapesTest(GeoBuildTestCase):
    def test_extracts_archives_and_writes_zip_outlines(self):
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        raw_dir = self.data_dir / "geo" / ".raw" / STATE
        for kind in ("cd", "sldu", "sldl", "county", "zcta"):
            self.assertTrue((raw_dir / f"{kind}.shp").is_file())
            self.assertTrue((raw_dir / f"{kind}.dbf").is_file())
            self.assertFalse((raw_dir / f"{kind}.zip").exists())
        # Zip outlines are found by the real field name, GEOID20.
        zcta_dir = self.data_dir / "geo" / STATE / "zcta"
        self.assertEqual(sorted(p.stem for p in zcta_dir.iterdir()),
                         ["99901", "99902", "99903", "99904"])

    def test_not_a_zip_archive(self):
        def fetch(url):
            if url == census_urls(STATE)["sldu.zip"]:
                return b"<html>not found</html>"
            return _fetch_from(self.src_dir)(url)
        with self.assertRaises(BuildError) as cm:
            _build(self.data_dir, STATE, fetch)
        self.assertIn("sldu.zip", str(cm.exception))
        self.assertIn("not a zip archive", str(cm.exception))
        raw_dir = self.data_dir / "geo" / ".raw" / STATE
        self.assertFalse((raw_dir / "sldu.zip").exists())

    def test_unknown_url_name(self):
        with self.assertRaises(BuildError) as cm:
            build(self.data_dir, STATE, _fetch_from(self.src_dir),
                  urls={"../escape": "https://x.test/"})
        self.assertIn("unknown download name", str(cm.exception))

    def test_without_sld_relationship_files(self):
        warnings = build(self.data_dir, STATE, _fetch_from(self.src_dir))
        self.assertEqual(len(warnings), 2)
        self.assertIn("sldu_rel.txt", warnings[0])
        self.assertIn("sldl_rel.txt", warnings[1])
        geo = GeoData.load(self.data_dir / "geo" / STATE)
        r = geo.zip_districts("99903")
        self.assertNotIn("sldu", r["kinds"])
        self.assertNotIn("sldl", r["kinds"])
        self.assertEqual(r["ambiguous"], ["cd"])
        # The shapes are still built, for the address fallback.
        self.assertIn("ocd-division/country:us/state:ca/sldu:1",
                      geo.district_shapes)

    def test_bad_relationship_header_is_a_build_error(self):
        def fetch(url):
            if url == census_urls(STATE)["cd_rel.txt"]:
                return b"<html>not found</html>\n"
            return _fetch_from(self.src_dir)(url)
        with self.assertRaises(BuildError) as cm:
            _build(self.data_dir, STATE, fetch)
        msg = str(cm.exception)
        self.assertIn("cd_rel.txt", msg)
        self.assertIn("GEOID_ZCTA5_20", msg)
        self.assertIn("--url cd_rel.txt=", msg)
        # Deleted, so the next run fetches it again and succeeds.
        raw_dir = self.data_dir / "geo" / ".raw" / STATE
        self.assertFalse((raw_dir / "cd_rel.txt").exists())
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        self.assertTrue((self.data_dir / "geo" / STATE / "zips.json").is_file())

    def test_given_sld_url_must_work(self):
        urls = {**geo_fixtures.SLD_REL_URLS,
                "sldu_rel.txt": "https://fixture.example.test/missing"}
        with self.assertRaises(BuildError) as cm:
            build(self.data_dir, STATE, _fetch_from(self.src_dir), urls=urls)
        self.assertIn("sldu_rel.txt", str(cm.exception))

    def test_relationship_skips_rows_outside_any_zcta(self):
        text = ("OID_ZCTA5_20|GEOID_ZCTA5_20|GEOID_COUNTY_20|AREALAND_PART\n"
                "|  |06999|\n"
                "1|99901|06999|1000\n")
        self.assertEqual(parse_relationship(text), [
            {"zip": "99901", "district_geoid": "06999",
             "area_land_part": 1000.0}])


class BuildInterruptedTest(GeoBuildTestCase):
    def test_build_interrupted_keeps_previous(self):
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        before = (self.data_dir / "geo" / STATE / "zips.json").read_bytes()
        # Corrupt an already-downloaded raw file so processing (not
        # fetching) fails on the second build.
        raw = self.data_dir / "geo" / ".raw" / STATE / "sldl.dbf"
        raw.write_bytes(b"not a dbf file")
        with self.assertRaises(Exception):
            _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        after = (self.data_dir / "geo" / STATE / "zips.json").read_bytes()
        self.assertEqual(before, after)
        self.assertFalse((self.data_dir / "geo" / f"{STATE}.tmp").exists())


class SimplifyTest(unittest.TestCase):
    def test_simplify(self):
        points = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0001),
                 (5.0, 0.0), (10.0, 10.0)]
        simplified = douglas_peucker(points, tolerance=0.01)
        self.assertEqual(simplified[0], points[0])
        self.assertEqual(simplified[-1], points[-1])
        # the collinear points (and the near-collinear one) are dropped.
        self.assertNotIn((1.0, 0.0), simplified)
        self.assertNotIn((2.0, 0.0), simplified)
        self.assertNotIn((3.0, 0.0001), simplified)

    def test_simplify_ring_drops_collapsed(self):
        tiny = [(0.0, 0.0), (0.00001, 0.0), (0.00002, 0.0), (0.0, 0.0)]
        self.assertIsNone(simplify_ring(tiny, tolerance=1.0))


class PointInPolygonTest(unittest.TestCase):
    SQUARE = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))

    def test_point_in_polygon(self):
        self.assertTrue(point_in_polygon((5.0, 5.0), [self.SQUARE]))
        self.assertFalse(point_in_polygon((15.0, 5.0), [self.SQUARE]))

    def test_point_in_polygon_hole(self):
        hole = ((3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0))
        rings = [self.SQUARE, hole]
        self.assertTrue(point_in_polygon((1.0, 1.0), rings))
        self.assertFalse(point_in_polygon((5.0, 5.0), rings))

    def test_point_in_multipolygon(self):
        other = ((20.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0))
        rings = [self.SQUARE, other]
        self.assertTrue(point_in_polygon((25.0, 5.0), rings))
        self.assertTrue(point_in_polygon((5.0, 5.0), rings))
        self.assertFalse(point_in_polygon((15.0, 5.0), rings))


class RowIntervalsTest(unittest.TestCase):
    def test_zero_width_shape_has_no_rows(self):
        # a line crosses this collapsed ring, but only at one x
        self.assertEqual(row_intervals([((0.0, 0.0), (0.0, 1.0))], 1.0), {})


class OcdIdTest(unittest.TestCase):
    def test_ocd_ids(self):
        cases = [
            ("cd", "0612", "ocd-division/country:us/state:ca/cd:12",
             "Congressional District 12"),
            ("sldu", "06011", "ocd-division/country:us/state:ca/sldu:11",
             "State Senate District 11"),
            ("sldl", "06017", "ocd-division/country:us/state:ca/sldl:17",
             "State Assembly District 17"),
        ]
        for kind, geoid, expect_id, expect_name in cases:
            with self.subTest(kind=kind):
                result = ocd_id(kind, geoid, "ca")
                self.assertEqual(result, (expect_id, expect_name))
        with self.subTest(kind="county"):
            result = ocd_id("county", "06075", "ca", "San Francisco")
            self.assertEqual(result, (
                "ocd-division/country:us/state:ca/county:san_francisco",
                "San Francisco County"))

    def test_ocd_id_skips_undefined(self):
        self.assertIsNone(ocd_id("cd", "06ZZ", "ca"))
        self.assertIsNone(ocd_id("sldu", "06ZZZ", "ca"))


class RelationshipColumnsTest(unittest.TestCase):
    def test_relationship_columns_by_name(self):
        text = "AREALAND_PART|GEOID_SLDL_20|GEOID_ZCTA5_20\n500|06001|90210\n"
        rows = parse_relationship(text)
        self.assertEqual(rows, [{"zip": "90210", "district_geoid": "06001",
                                 "area_land_part": 500.0}])


class ZipLookupTest(GeoBuildTestCase):
    def setUp(self):
        super().setUp()
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))
        self.geo = GeoData.load(self.data_dir / "geo" / STATE)

    def test_zip_lookup(self):
        r1 = self.geo.zip_districts("99901")
        self.assertEqual(r1["ambiguous"], [])
        for kind in ("state", "cd", "sldu", "sldl", "county"):
            self.assertEqual(len(r1["kinds"][kind]), 1)

        r2 = self.geo.zip_districts("99902")
        self.assertEqual(r2["ambiguous"], ["cd"])
        self.assertEqual(len(r2["kinds"]["cd"]), 2)

        r3 = self.geo.zip_districts("99903")
        self.assertEqual(r3["ambiguous"], ["cd", "sldu"])

    def test_min_overlap(self):
        r4 = self.geo.zip_districts("99904")
        self.assertIn("cd", r4["ambiguous"])
        self.assertEqual(len(r4["kinds"]["cd"]), 2)

        filtered_dir = self.root / "data_filtered"
        _build(filtered_dir, STATE, _fetch_from(self.src_dir), min_overlap=0.01)
        geo2 = GeoData.load(filtered_dir / "geo" / STATE)
        r4b = geo2.zip_districts("99904")
        self.assertNotIn("cd", r4b["ambiguous"])
        self.assertEqual(len(r4b["kinds"]["cd"]), 1)

    def test_unknown_zip(self):
        self.assertIsNone(self.geo.zip_districts("00000"))


class GeoZipCliTest(GeoBuildTestCase):
    def setUp(self):
        super().setUp()
        _build(self.data_dir, STATE, _fetch_from(self.src_dir))

    def test_geo_zip_cli(self):
        out = io.StringIO()
        code = main(["geo", "zip", "99902", "--state", STATE,
                    "--data-dir", str(self.data_dir)], out=out)
        self.assertEqual(code, 0)
        lines = out.getvalue().splitlines()
        cd_lines = [l for l in lines if l.startswith("cd\t")]
        self.assertEqual(len(cd_lines), 2)

    def test_geo_zip_cli_unknown(self):
        out = io.StringIO()
        code = main(["geo", "zip", "00000", "--state", STATE,
                    "--data-dir", str(self.data_dir)], out=out)
        self.assertEqual(code, 1)


class ShapefileReaderTest(unittest.TestCase):
    def test_shapefile_reader(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name) / "shapes"
        outer = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        hole = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0), (3.0, 3.0)]
        part_a = [(20.0, 0.0), (25.0, 0.0), (25.0, 5.0), (20.0, 5.0), (20.0, 0.0)]
        part_b = [(30.0, 0.0), (35.0, 0.0), (35.0, 5.0), (30.0, 5.0), (30.0, 0.0)]
        geo_fixtures.write_shapefile(
            base, [("GEOID", "C", 10)],
            [{"GEOID": "with-hole"}, {"GEOID": "multi-part"}],
            [[outer, hole], [part_a, part_b]])
        records = read_shapefile(base)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].attrs["GEOID"], "with-hole")
        self.assertEqual(len(records[0].rings), 2)
        self.assertEqual(len(records[0].rings[0]), 5)
        self.assertEqual(len(records[0].rings[1]), 5)
        self.assertEqual(records[1].attrs["GEOID"], "multi-part")
        self.assertEqual(len(records[1].rings), 2)


if __name__ == "__main__":
    unittest.main()
