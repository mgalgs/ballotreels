"""Related measures (data/related.toml): the loader, the data file
itself, and the list each measure's API answer carries."""

import json
import tempfile
import unittest
from pathlib import Path

from ballotreels.index import load_index
from ballotreels.related import (RelatedError, load_related, related_to,
                                 unknown_ids)
from ballotreels.site.server import _contest_detail, build_deps

from .helpers import REPO
from .test_serve_public import _make_config
from .test_short_urls import ShortUrlTestCase

DATA = REPO / "data"


def _groups(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "related.toml"
        path.write_text(text, encoding="utf-8")
        return load_related(path)


class LoaderTest(unittest.TestCase):
    def test_symmetric(self):
        groups = _groups('g = ["a", "b", "c"]\n')
        self.assertEqual(related_to(groups, "a"), {"b", "c"})
        self.assertEqual(related_to(groups, "b"), {"a", "c"})
        self.assertEqual(related_to(groups, "c"), {"a", "b"})

    def test_pair_in_two_groups_once(self):
        groups = _groups('g = ["a", "b"]\nh = ["b", "a", "c"]\n'
                         'i = ["d", "c"]\n')
        self.assertEqual(related_to(groups, "a"), {"b", "c"})
        self.assertEqual(related_to(groups, "c"), {"a", "b", "d"})

    def test_none(self):
        # A group of one, a measure in no group, an empty file and no
        # file at all: nothing related.
        groups = _groups('g = ["a"]\nh = ["b", "c"]\n')
        self.assertEqual(related_to(groups, "a"), set())
        self.assertEqual(related_to(groups, "z"), set())
        self.assertEqual(related_to(_groups(""), "a"), set())
        self.assertEqual(load_related(Path("/nonexistent/related.toml")), {})

    def test_repeated_id_fails(self):
        with self.assertRaisesRegex(RelatedError, "'g': repeats a"):
            _groups('g = ["a", "b", "a"]\n')

    def test_not_a_list_fails(self):
        for text in ('g = "a"\n', 'g = ["a", 1]\n', '[g]\nids = ["a"]\n'):
            with self.subTest(text), self.assertRaises(RelatedError):
                _groups(text)

    def test_unknown_ids(self):
        groups = _groups('g = ["a", "x"]\nh = ["x", "y", "b"]\n')
        self.assertEqual(unknown_ids(groups, {"a", "b"}), ["x", "y"])


class DataFileTest(unittest.TestCase):
    def test_every_id_is_a_loaded_contest(self):
        # load_related itself fails on a group that repeats an id.
        groups = load_related(DATA / "related.toml")
        self.assertTrue(groups)
        known = {e.id for p in DATA.glob("*/contests.toml")
                 for e in load_index(p.parent).entries}
        self.assertEqual(unknown_ids(groups, known), [])


class RealDataApiTest(unittest.TestCase):
    """The API's list over the real data, as the served site has it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.deps = build_deps(_make_config(Path(cls.tmp.name), election=None),
                              warn=lambda m: None)

    @classmethod
    def tearDownClass(cls):
        cls.deps.queue.close()
        cls.tmp.cleanup()

    def related(self, contest_id):
        state, entry = self.deps.contest(contest_id)
        return [(r["state_name"], r["id"])
                for r in _contest_detail(entry, state, self.deps)["related"]]

    def test_voter_identification_links_both_ways(self):
        self.assertEqual(self.related("ca-2026-11-03-prop-39"),
                         [("Arizona", "az-2026-11-03-prop-144"),
                          ("Ohio", "oh-2026-11-03-issue-3")])
        self.assertEqual(self.related("oh-2026-11-03-issue-3"),
                         [("Arizona", "az-2026-11-03-prop-144"),
                          ("California", "ca-2026-11-03-prop-39")])
        self.assertEqual(self.related("az-2026-11-03-prop-144"),
                         [("California", "ca-2026-11-03-prop-39"),
                          ("Ohio", "oh-2026-11-03-issue-3")])

    def test_own_state_first(self):
        self.assertEqual(self.related("fl-2026-11-03-amendment-2"),
                         [("Florida", "fl-2026-11-03-amendment-3"),
                          ("California", "ca-2026-11-03-prop-42")])

    def test_two_groups_and_lone_groups(self):
        # Utah's Amendment B is in two groups; the other has only it.
        self.assertEqual(self.related("ut-2026-11-03-amendment-b"),
                         [("California", "ca-2026-11-03-prop-43")])
        self.assertEqual(self.related("ca-2026-11-03-prop-4"), [])

    def test_unrelated_measure(self):
        self.assertEqual(self.related("ca-2026-11-03-prop-5"), [])

    def test_fields(self):
        state, entry = self.deps.contest("ca-2026-11-03-prop-39")
        [az, _] = _contest_detail(entry, state, self.deps)["related"]
        other_state, other = self.deps.contest("az-2026-11-03-prop-144")
        self.assertEqual(az, {
            "id": "az-2026-11-03-prop-144", "state": "az",
            "state_name": "Arizona",
            # As contests.toml prints it, and as its own page heads it.
            "title": other.title,
            "path": "/az/2026/prop-144",
        })


class RelatedApiTest(ShortUrlTestCase):
    """Order over fixture elections, through the served API."""

    def setUp(self):
        super().setUp()
        # In neither file nor ballot order; Texas has no measures.
        self.deps.related = {"g": ("ut-2026-11-03-amendment-a",
                                   "ca-2026-11-03-cd-1",
                                   "ca-2026-11-03-prop-9",
                                   "ca-2026-11-03-prop-3",
                                   "tx-2026-11-03-gone")}

    def api(self, path):
        resp, body = self.request(path)
        self.assertEqual(resp.status, 200)
        return json.loads(body)

    def test_order(self):
        doc = self.api("/api/contest/ca/2026/prop-9")
        self.assertEqual([r["path"] for r in doc["related"]],
                         ["/ca/2026/prop-3", "/ca/2026/cd-1",
                          "/ut/2026/amendment-a"])
        doc = self.api("/api/contest/ut-2026-11-03-amendment-a")
        self.assertEqual([r["path"] for r in doc["related"]],
                         ["/ca/2026/prop-3", "/ca/2026/prop-9",
                          "/ca/2026/cd-1"])

    def test_empty(self):
        self.deps.related = {}
        doc = self.api("/api/contest/ca/2026/prop-9")
        self.assertEqual(doc["related"], [])


if __name__ == "__main__":
    unittest.main()
