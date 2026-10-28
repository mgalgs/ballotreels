"""An election's divisions.tsv: written from the geo build, and the check
that refuses a local contest whose division is not in it."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from ballotreels.cli import main

from . import geo_fixtures

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


if __name__ == "__main__":
    unittest.main()
