import shutil
import tempfile
import unittest
from pathlib import Path

from ballotreels.index import ContestIndexError, ballot_order, key_for, load_index
from ballotreels.standard import load_standard

from .helpers import REPO

FIXTURE = REPO / "tests" / "fixtures" / "contests" / "ca-2026-11-03"
REAL = REPO / "data" / "ca-2026-11-03"


class ScratchIndexTestCase(unittest.TestCase):
    """A scratch copy of the fixture election dir to break."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "ca-2026-11-03"
        shutil.copytree(FIXTURE, self.dir)

    def write(self, text):
        (self.dir / "contests.toml").write_text(text, encoding="utf-8")


BASE = """
[election]
id = "ca-2026-11-03"
state = "ocd-division/country:us/state:ca"
title = "Test Election"
"""


class IndexTest(unittest.TestCase):
    def test_prop_2_seeded(self):
        index = load_index(REAL)
        self.assertEqual(index.election.id, "ca-2026-11-03")
        self.assertEqual(len(index.entries), 1)
        entry = index.entries[0]
        self.assertEqual(entry.id, "ca-2026-11-03-prop-2")
        self.assertEqual(entry.division, "ocd-division/country:us/state:ca")
        self.assertEqual(entry.kind, "measure")
        self.assertEqual(entry.number, "2")

    def test_key_for(self):
        index = load_index(FIXTURE)
        standard = load_standard()
        measure = index.get("ca-2026-11-03-prop-90")
        race = index.get("ca-2026-11-03-assembly-17")
        self.assertEqual(
            key_for(index.election.id, measure, standard),
            ("ca-2026-11-03", "ocd-division/country:us/state:ca",
             "ca-2026-11-03-prop-90", standard.version, 2))
        self.assertIsNone(key_for(index.election.id, race, standard))

    def test_ballot_order(self):
        index = load_index(FIXTURE)
        order = [e.id for e in ballot_order(index)]
        self.assertEqual(order, [
            "ca-2026-11-03-prop-92",
            "ca-2026-11-03-prop-90",
            "ca-2026-11-03-prop-91",
            "ca-2026-11-03-assembly-17",
        ])


class IndexErrorTest(ScratchIndexTestCase):
    def test_duplicate_id(self):
        self.write(BASE + """
[[contest]]
id = "ca-2026-11-03-prop-90"
kind = "measure"
division = "ocd-division/country:us/state:ca"
title = "A"
number = "90"

[[contest]]
id = "ca-2026-11-03-prop-90"
kind = "measure"
division = "ocd-division/country:us/state:ca"
title = "B"
number = "90"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("duplicate id", str(cm.exception))

    def test_bad_kind(self):
        self.write(BASE + """
[[contest]]
id = "ca-2026-11-03-prop-90"
kind = "referendum"
division = "ocd-division/country:us/state:ca"
title = "A"
number = "90"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("kind", str(cm.exception))

    def test_measure_without_number(self):
        self.write(BASE + """
[[contest]]
id = "ca-2026-11-03-prop-90"
kind = "measure"
division = "ocd-division/country:us/state:ca"
title = "A"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("needs 'number'", str(cm.exception))

    def test_race_without_office(self):
        self.write(BASE + """
[[contest]]
id = "ca-2026-11-03-assembly-17"
kind = "race"
division = "ocd-division/country:us/state:ca/sldl:17"
title = "A"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("needs 'office'", str(cm.exception))

    def test_id_without_election_prefix(self):
        self.write(BASE + """
[[contest]]
id = "prop-90"
kind = "measure"
division = "ocd-division/country:us/state:ca"
title = "A"
number = "90"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("must start with", str(cm.exception))

    def test_division_not_ocd(self):
        self.write(BASE + """
[[contest]]
id = "ca-2026-11-03-prop-90"
kind = "measure"
division = "california"
title = "A"
number = "90"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("ocd-division/", str(cm.exception))

    def test_mismatch_with_sources_toml(self):
        contest_dir = self.dir / "prop-90"
        contest_dir.mkdir()
        (contest_dir / "sources.toml").write_text("""
[contest]
id = "ca-2026-11-03-prop-90"
election = "ca-2026-11-03"
division = "ocd-division/country:us/state:ca/cd:5"
kind = "measure"
title = "whatever"
""", encoding="utf-8")
        self.write(BASE + """
[[contest]]
id = "ca-2026-11-03-prop-90"
kind = "measure"
division = "ocd-division/country:us/state:ca"
title = "A"
number = "90"
""")
        with self.assertRaises(ContestIndexError) as cm:
            load_index(self.dir)
        self.assertIn("does not match", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
