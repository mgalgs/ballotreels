"""Related measures (data/related.toml): the loader, the data file
itself, and the list each measure's API answer carries."""

import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from ballotreels.index import load_index
from ballotreels.related import (RelatedError, load_related, related_to,
                                 unknown_ids)
from ballotreels.site.server import _contest_detail, build_deps

from .helpers import REPO
from .test_serve_public import _make_config
from .test_short_urls import TRICKY, ShortUrlTestCase

DATA = REPO / "data"
APP_JS = REPO / "ballotreels" / "site" / "static" / "app.js"


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
                          ("Nevada", "nv-2026-11-03-question-7"),
                          ("Ohio", "oh-2026-11-03-issue-3")])
        self.assertEqual(self.related("oh-2026-11-03-issue-3"),
                         [("Arizona", "az-2026-11-03-prop-144"),
                          ("California", "ca-2026-11-03-prop-39"),
                          ("Nevada", "nv-2026-11-03-question-7")])
        self.assertEqual(self.related("az-2026-11-03-prop-144"),
                         [("California", "ca-2026-11-03-prop-39"),
                          ("Nevada", "nv-2026-11-03-question-7"),
                          ("Ohio", "oh-2026-11-03-issue-3")])
        self.assertEqual(self.related("nv-2026-11-03-question-7"),
                         [("Arizona", "az-2026-11-03-prop-144"),
                          ("California", "ca-2026-11-03-prop-39"),
                          ("Ohio", "oh-2026-11-03-issue-3")])

    def test_own_state_first(self):
        self.assertEqual(self.related("fl-2026-11-03-amendment-2"),
                         [("Florida", "fl-2026-11-03-amendment-3"),
                          ("California", "ca-2026-11-03-prop-42"),
                          ("Wyoming", "wy-2026-11-03-initiative-proposition-1")])

    def test_two_groups(self):
        # Utah's Amendment B is in two groups, one link from each.
        self.assertEqual(self.related("ut-2026-11-03-amendment-b"),
                         [("California", "ca-2026-11-03-prop-43"),
                          ("Montana", "mt-2026-11-03-ci-133")])

    def test_unrelated_measure(self):
        self.assertEqual(self.related("ca-2026-11-03-prop-5"), [])

    def test_fields(self):
        state, entry = self.deps.contest("ca-2026-11-03-prop-39")
        [az, *_] = _contest_detail(entry, state, self.deps)["related"]
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


class _Related(HTMLParser):
    """A page's related-measures section: its heading, and each link's
    href, state name and title."""

    def __init__(self):
        super().__init__()
        self.sections = 0
        self.heading = ""
        self.links = []
        self._in = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("class") == "related-measures":
            self.sections += 1
            self._depth = 1
            return
        if not self._depth:
            return
        if tag == "section":
            self._depth += 1
        if tag == "h2":
            self._in = "heading"
        elif tag == "a":
            self.links.append([attrs["href"], "", ""])
        elif attrs.get("class") == "related-state":
            self._in = 1
        elif attrs.get("class") == "related-title":
            self._in = 2

    def handle_endtag(self, tag):
        if self._depth and tag == "section":
            self._depth -= 1
        if tag in ("h2", "span"):
            self._in = None

    def handle_data(self, data):
        if self._in == "heading":
            self.heading += data
        elif self._in in (1, 2):
            self.links[-1][self._in] += data


def _parse(html):
    parser = _Related()
    parser.feed(html)
    return parser


# Runs app.js's relatedSection under node with a minimal stand-in for the
# DOM, over the API's "related" list (argv[2]), and prints its HTML.
RELATED_HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
function node(tag) {
  return {
    tag, attrs: {}, children: [], textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener() {},
    get outerHTML() {
      if (this.tag === "#text") return esc(this.text);
      const attrs = Object.entries(this.attrs)
        .map(([k, v]) => ` ${k}="${esc(v)}"`).join("");
      return `<${this.tag}${attrs}>${esc(this.textContent)}` +
        this.children.map((c) => c.outerHTML).join("") + `</${this.tag}>`;
    },
  };
}
globalThis.document = {
  createElement: node,
  createTextNode: (text) => ({ tag: "#text", text, children: [],
                               get outerHTML() { return esc(text); } }),
};
const fn = (name) => src.match(
  new RegExp(`function ${name}\\([\\s\\S]*?\\n}\\n`))[0];
eval(fn("el") + fn("heading") + fn("relatedSection") +
     "; globalThis.relatedSection = relatedSection;");
const section = relatedSection(JSON.parse(process.argv[2]));
console.log(section ? section.outerHTML : "");
"""


def _in_app(related):
    return subprocess.run(
        ["node", "-e", RELATED_HARNESS, str(APP_JS), json.dumps(related)],
        check=True, capture_output=True, text=True).stdout


class RenderingsTest(RelatedApiTest):
    """The page the server sends and the page the app draws list the same
    related measures, in the same order, under the same heading."""

    def server_page(self, path):
        resp, body = self.request(path)
        self.assertEqual(resp.status, 200)
        return _parse(body.decode("utf-8"))

    def test_server_page(self):
        page = self.server_page("/ca/2026/prop-3")
        self.assertEqual(page.sections, 1)
        self.assertEqual(page.heading, "Related measures")
        self.assertEqual(page.links, [
            # The title as contests.toml has it, escaped and unescaped
            # again intact.
            ["/ca/2026/prop-9", "California", TRICKY + "."],
            ["/ca/2026/cd-1", "California",
             "Fake California District Measure"],
            ["/ut/2026/amendment-a", "Utah",
             "Constitutional Amendment A: Fake"]])

    def test_none_without_related(self):
        self.deps.related = {"g": ("ca-2026-11-03-prop-3",)}
        for path in ("/ca/2026/prop-3", "/ca/2026/prop-9", "/ca", "/",
                     "/ca/2026/no-such-measure"):
            with self.subTest(path):
                resp, body = self.request(path)
                self.assertNotIn(b"related-measures", body)
                self.assertNotIn(b"Related measures", body)

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_app_matches_server(self):
        for path in ("/ca/2026/prop-3", "/ca/2026/prop-9",
                     "/ut/2026/amendment-a"):
            with self.subTest(path):
                related = self.api("/api/contest" + path)["related"]
                app = _parse(_in_app(related))
                server = self.server_page(path)
                self.assertEqual(app.sections, 1)
                self.assertEqual(app.heading, server.heading)
                self.assertEqual(app.links, server.links)
                self.assertEqual([link[0] for link in app.links],
                                 [r["path"] for r in related])

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_app_draws_nothing_without_related(self):
        self.assertEqual(_in_app([]).strip(), "")

    def test_app_places_it_after_the_measure(self):
        src = APP_JS.read_text(encoding="utf-8")
        page = src[src.index("async function renderContest"):]
        self.assertLess(page.index("rest.appendChild(corrections)"),
                        page.index("relatedSection(body.related)"))
        self.assertLess(page.index("relatedSection(body.related)"),
                        page.index('"fine-print"'))


if __name__ == "__main__":
    unittest.main()
