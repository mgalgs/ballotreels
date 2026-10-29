"""An election's divisions.tsv: written from the geo build, and the check
that refuses a local contest whose division is not in it."""

import io
import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from ballotreels import check_contest, load_contest
from ballotreels.checks import check_division
from ballotreels.cli import main
from ballotreels.pipeline import run_check

from . import geo_fixtures
from .helpers import PROP_2, unlinted_standard

CA = "ocd-division/country:us/state:ca"


class WriteDivisionsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data_dir = self.root / "var"
        self.election = self.root / "ca-2026-11-03"
        self.election.mkdir()

    def run_cli(self, *args):
        out = io.StringIO()
        code = main(["geo", "divisions", str(self.election),
                     "--data-dir", str(self.data_dir), *args], out=out)
        return code, out.getvalue()

    def test_writes_every_local_shape_sorted(self):
        geo_fixtures.build_local_geo(self.data_dir)
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        # Spring Valley is a CDP (no government) and 99999 is no school
        # district: the build has no shape for either, so neither is here.
        self.assertEqual(
            (self.election / "divisions.tsv").read_bytes().decode("utf-8"),
            f"{CA}/county:imperial\tImperial County\n"
            f"{CA}/county:san_diego\tSan Diego County\n"
            f"{CA}/place:el_cajon\tCity of El Cajon\n"
            f"{CA}/place:san_diego\tCity of San Diego\n"
            f"{CA}/school_district:cajon_valley_union_school_district\t"
            f"Cajon Valley Union School District\n"
            f"{CA}/school_district:grossmont_union_high_school_district\t"
            f"Grossmont Union High School District\n"
            f"{CA}/school_district:san_diego_unified_school_district\t"
            f"San Diego Unified School District\n")

    def test_one_line_per_shape(self):
        # Two school districts of one name (in different counties) are
        # two shapes and two lines, as in the committed CA file.
        geo_dir = self.data_dir / "geo" / "ca"
        geo_dir.mkdir(parents=True)

        def write(level, names):
            features = [{"type": "Feature",
                         "properties": {"ocd_id": f"{CA}/{level}:{slug}",
                                        "name": name, "kind": level},
                         "geometry": None} for slug, name in names]
            (geo_dir / f"{level}.geojson").write_text(json.dumps(
                {"type": "FeatureCollection", "features": features}),
                encoding="utf-8")
        write("county", [("yolo", "Yolo County")])
        write("place", [])
        write("school_district",
              [("liberty_elementary_school_district",
                "Liberty Elementary School District"),
               ("abc_unified_school_district", "ABC Unified School District"),
               ("liberty_elementary_school_district",
                "Liberty Elementary School District")])
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        self.assertEqual(
            (self.election / "divisions.tsv").read_text(encoding="utf-8"),
            f"{CA}/county:yolo\tYolo County\n"
            f"{CA}/school_district:abc_unified_school_district\t"
            f"ABC Unified School District\n"
            f"{CA}/school_district:liberty_elementary_school_district\t"
            f"Liberty Elementary School District\n"
            f"{CA}/school_district:liberty_elementary_school_district\t"
            f"Liberty Elementary School District\n")

    def test_no_geo_build_fails(self):
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("county.geojson", out)
        self.assertIn("geo build", out)
        self.assertFalse((self.election / "divisions.tsv").exists())


SAN_DIEGO_UNIFIED = f"{CA}/school_district:san_diego_city_unified_school_district"


class CheckDivisionTest(unittest.TestCase):
    """check_division reads only a contest's id, division and directory,
    so these are Prop 2 moved into a scratch election and given another
    division."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.election = Path(tmp.name) / "ca-2026-11-03"
        self.election.mkdir()
        (self.election / "divisions.tsv").write_text(
            f"{CA}/county:san_diego\tSan Diego County\n"
            f"{CA}/place:san_diego\tCity of San Diego\n"
            f"{CA}/school_district:san_diego_city_unified_school_district\t"
            f"San Diego City Unified School District\n"
            f"{CA}/school_district:san_dieguito_union_high_school_district\t"
            f"San Dieguito Union High School District\n"
            f"{CA}/school_district:santee_school_district\t"
            f"Santee School District\n", encoding="utf-8")
        self.prop_2 = load_contest(PROP_2)

    def contest(self, division, election=None):
        return replace(self.prop_2, id="ca-2026-11-03-measure-m",
                       division=division,
                       path=(election or self.election) / "measure-m")

    def test_listed_school_district_passes(self):
        self.assertEqual(check_division(self.contest(SAN_DIEGO_UNIFIED)), [])

    def test_ballot_name_fails_with_the_tiger_name(self):
        wrong = f"{CA}/school_district:san_diego_unified_school_district"
        failures = check_division(self.contest(wrong))
        self.assertEqual(len(failures), 1)
        message = str(failures[0])
        self.assertTrue(message.startswith("[division] "), message)
        self.assertIn("ca-2026-11-03-measure-m", message)
        self.assertIn(repr(wrong), message)
        # the closest of the same level first; never the county or city
        self.assertIn(f"closest listed: {SAN_DIEGO_UNIFIED!r} "
                      f"(San Diego City Unified School District)", message)
        self.assertNotIn("county:", message)
        self.assertNotIn("place:", message)

    def test_unlisted_place_and_county_fail(self):
        for division in (f"{CA}/place:san_deigo", f"{CA}/county:sandiego"):
            failures = check_division(self.contest(division))
            self.assertEqual(len(failures), 1, division)
            self.assertIn("closest listed", failures[0].message)

    def test_nothing_close(self):
        failures = check_division(self.contest(f"{CA}/place:zzyzx"))
        self.assertIn("no listed place is close", failures[0].message)

    def test_missing_file_fails(self):
        (self.election / "divisions.tsv").unlink()
        failures = check_division(self.contest(SAN_DIEGO_UNIFIED))
        self.assertEqual(len(failures), 1)
        self.assertIn("no divisions.tsv", failures[0].message)
        self.assertIn("python -m ballotreels geo divisions ca-2026-11-03",
                      failures[0].message)

    def test_other_levels_need_no_file(self):
        (self.election / "divisions.tsv").unlink()
        for division in (CA, f"{CA}/cd:51", f"{CA}/sldu:39"):
            self.assertEqual(check_division(self.contest(division)), [],
                             division)

    def test_statewide_contest_passes_every_check_without_the_file(self):
        # Prop 2's own election (tests/fixtures) has no divisions.tsv.
        self.assertFalse((PROP_2.parent / "divisions.tsv").exists())
        self.assertEqual(
            check_contest(self.prop_2, unlinted_standard()), [])

    def local_prop_2(self, parent, division=SAN_DIEGO_UNIFIED):
        """Prop 2's files under `parent`, with a local division."""
        dest = parent / "prop-2"
        shutil.copytree(PROP_2, dest)
        sources = dest / "sources.toml"
        sources.write_text(sources.read_text(encoding="utf-8").replace(
            f'division = "{CA}"\n', f'division = "{division}"\n', 1),
            encoding="utf-8")
        return dest

    def test_cli_check_runs_it(self):
        wrong = f"{CA}/school_district:san_diego_unified_school_district"
        out = io.StringIO()
        code = main(["check", str(self.local_prop_2(self.election, wrong))],
                    out=out)
        self.assertNotEqual(code, 0)
        self.assertIn(f"[division] ca-2026-11-03-prop-2: division "
                      f"{wrong!r}", out.getvalue())

    def test_cli_check_refuses_the_9_12_territory(self):
        # The geo build lists the 9-12 piece as a shape of its own, but a
        # voter there sees the district's contests: name the district.
        piece = f"{SAN_DIEGO_UNIFIED}_9-12"
        with (self.election / "divisions.tsv").open(
                "a", encoding="utf-8") as f:
            f.write(f"{piece}\tSan Diego City Unified School District\n")
        contest_dir = self.local_prop_2(self.election, piece)
        out = io.StringIO()
        code = main(["check", str(contest_dir)], out=out)
        self.assertNotEqual(code, 0)
        self.assertIn(f"[division] ca-2026-11-03-prop-2: division "
                      f"{piece!r} is only the district's 9-12 territory",
                      out.getvalue())
        self.assertIn(f"use the plain district division "
                      f"{SAN_DIEGO_UNIFIED!r}", out.getvalue())

        # The same contest naming the district passes the rule.
        sources = contest_dir / "sources.toml"
        sources.write_text(sources.read_text(encoding="utf-8").replace(
            piece, SAN_DIEGO_UNIFIED), encoding="utf-8")
        self.assertEqual(check_division(load_contest(contest_dir)), [])
        out = io.StringIO()
        main(["check", str(contest_dir)], out=out)
        self.assertNotIn("[division]", out.getvalue())

    def test_film_check_of_a_scratch_copy_passes(self):
        # The worker checks a copy at <work_dir>/<job_id>/<dir>, with no
        # election (and so no divisions.tsv) around it.
        scratch = self.election.parent / "42"
        scratch.mkdir()
        run_check(self.local_prop_2(scratch), unlinted_standard())
        self.assertEqual([f for f in check_contest(
            self.contest(SAN_DIEGO_UNIFIED, election=scratch),
            unlinted_standard()) if f.check == "division"], [])

if __name__ == "__main__":
    unittest.main()
