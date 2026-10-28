import json
import shutil
import subprocess
import urllib.parse
import re
import unittest

from ballotreels.standard import judgment_word_pattern, load_standard

from .helpers import REPO
from .test_serve_public import ServerTestCase

STATIC_DIR = REPO / "ballotreels" / "site" / "static"
FILM_MEASURE = (REPO / "film" / "measure.py").read_text(encoding="utf-8")

PARTY_WORDS = ("democrat", "republican", "party", "gop", "liberal",
              "conservative")
PARTY_PATTERN = re.compile(
    r"(?<!\w)(?:" + "|".join(PARTY_WORDS) + r")(?!\w)", re.IGNORECASE)

SITE_FILES = ("index.html", "app.js", "admin.html", "admin.js", "login.html",
             "style.css")


class StaticFilesTest(ServerTestCase):
    def test_static_files(self):
        resp, body = self.get(self.public_port, "/")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"<html", body)

        resp, body = self.get(self.public_port, "/static/app.js")
        self.assertEqual(resp.status, 200)
        self.assertIn("javascript", resp.getheader("Content-Type"))

        resp, body = self.get(self.public_port, "/static/style.css")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/css", resp.getheader("Content-Type"))
        self.assertEqual(resp.getheader("Cache-Control"), "no-cache")

    def test_static_traversal(self):
        resp, body = self.get(self.public_port, "/static/../server.py")
        self.assertEqual(resp.status, 404)
        resp, body = self.get(self.public_port, "/static/..%2f..%2fcli.py")
        self.assertEqual(resp.status, 404)


class FooterMatchesVideoTest(unittest.TestCase):
    def test_footer_matches_video(self):
        m = re.search(r"FOOTER = '([^']*)'", FILM_MEASURE)
        self.assertIsNotNone(m, "FOOTER constant not found in film/measure.py")
        footer = m.group(1)
        index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn(footer, index_html)


class SiteCopyNeutralTest(unittest.TestCase):
    def test_site_copy_neutral(self):
        standard = load_standard()
        pattern = judgment_word_pattern(standard.judgment_words)
        for name in SITE_FILES:
            text = (STATIC_DIR / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                judgment_hits = [m.group(0) for m in pattern.finditer(text)]
                self.assertEqual(judgment_hits, [])
                party_hits = [m.group(0) for m in PARTY_PATTERN.finditer(text)]
                self.assertEqual(party_hits, [])


class OneMapColourTest(unittest.TestCase):
    def test_one_map_colour(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        m = re.search(r'const MAP_COLOR = "(#[0-9a-fA-F]{3,8})"', app_js)
        self.assertIsNotNone(m, "MAP_COLOR constant not found")
        map_color = m.group(1)
        # Every other usage references the MAP_COLOR constant, not a
        # second hex literal, so the only hex colour in the file is the
        # one definition.
        all_colors = re.findall(r"#[0-9a-fA-F]{3,8}", app_js)
        self.assertEqual(set(all_colors), {map_color})
        self.assertGreaterEqual(app_js.count("MAP_COLOR"), 3)
        # Neutral: a grey, not a hue a reader could take for a party's
        # red or blue (STANDARD.md rule 4.1).
        hex_digits = map_color[1:]
        if len(hex_digits) == 3:
            hex_digits = "".join(c * 2 for c in hex_digits)
        r, g, b = (int(hex_digits[i:i + 2], 16) for i in (0, 2, 4))
        self.assertLessEqual(max(r, g, b) - min(r, g, b), 16)


class ContestApiFieldsTest(ServerTestCase):
    def test_contest_api_fields(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        for needle in ("report_url", "sources", "standard_version",
                      "corrections"):
            self.assertIn(needle, app_js)

        resp, body = self.get(self.public_port,
                              "/api/contest/ca-2026-11-03-prop-90")
        import json
        doc = json.loads(body)
        self.assertEqual(doc["report_url"],
                         "https://github.com/mgalgs/ballotreels/issues")
        for field in ("sources", "standard_version", "corrections"):
            self.assertIn(field, doc)


class MapLeafletAndFallbackTest(unittest.TestCase):
    def test_map_leaflet_and_fallback(self):
        index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        m = re.search(r'<script[^>]*leaflet[^>]*integrity="[^"]+"', index_html)
        self.assertIsNotNone(m, "Leaflet script tag missing an integrity attr")
        self.assertIn("OpenStreetMap", index_html)

        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertRegex(app_js, r"typeof\s+L\s*===\s*['\"]undefined['\"]")

    def test_leaflet_sri_hashes_are_the_published_ones(self):
        # Leaflet 1.9.4's published SRI hashes (leafletjs.com/download):
        # a wrong one makes the browser block the file.
        index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("leaflet@1.9.4/dist/leaflet.css", index_html)
        self.assertIn(
            'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="',
            index_html)
        self.assertIn(
            'integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="',
            index_html)

    def test_map_districts_are_tappable(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        # Leaflet layers and SVG fallback polygons both select on tap.
        self.assertIn('layer.on("click"', app_js)
        self.assertIn('poly.addEventListener("click"', app_js)
        self.assertRegex(app_js, r"drawMap\(mapDiv, shapes,\s*\(ocdId\) =>")


if __name__ == "__main__":
    unittest.main()


# Runs app.js's selectDistrict under node with stubbed routing, for a zip
# ambiguous on two kinds: the first choice must reach the ballot, and so
# must the zip's partial cities and school districts.
SELECT_DISTRICT_HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const fn = src.match(/function selectDistrict[\s\S]*?\n}\n/)[0] +
  src.match(/function ballotParams[\s\S]*?\n}\n/)[0];
const location = { hash: "" };
const go = (href) => { location.hash = href.replace(/^\//, ""); };
let next = null;
const renderAmbiguousKind = (zip, doc, kind) => { next = [doc, kind]; };
eval(fn);
const doc = {
  kinds: { state: [{ ocd_id: "S" }],
           cd: [{ ocd_id: "cd:1" }, { ocd_id: "cd:2" }],
           sldl: [{ ocd_id: "sldl:1" }, { ocd_id: "sldl:2" }],
           place: [{ ocd_id: "place:a" }, { ocd_id: "place:b" }] },
  ambiguous: ["cd", "sldl"],
  partial: ["place:a", "place:b"],
};
selectDistrict("99903", doc, "cd", "cd:1");
selectDistrict("99903", next[0], next[1], "sldl:2");
console.log(JSON.stringify({ kind: next[1], hash: location.hash }));
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class SelectDistrictTest(unittest.TestCase):
    def test_choices_carry_across_ambiguous_kinds(self):
        out = subprocess.run(
            ["node", "-e", SELECT_DISTRICT_HARNESS,
             str(STATIC_DIR / "app.js")],
            check=True, capture_output=True, text=True).stdout
        result = json.loads(out)
        self.assertEqual(result["kind"], "sldl")
        params = urllib.parse.parse_qs(result["hash"].split("?", 1)[1])
        self.assertEqual(sorted(params["d"]),
                         ["S", "cd:1", "place:a", "place:b", "sldl:2"])
        self.assertEqual(sorted(params["p"]), ["place:a", "place:b"])


# Runs app.js's titleParts under node over every designation style the
# states served write, printing {title: [eyebrow, rest]}.
TITLE_PARTS_HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const start = src.indexOf("const DESIGNATION =");
const end = src.indexOf("function contestHeading");
eval(src.slice(start, end) + "; globalThis.titleParts = titleParts;");
const out = {};
for (const title of JSON.parse(process.argv[2])) {
  const parts = titleParts({ title, kind: "measure", number: null });
  out[title] = [parts.eyebrow, parts.title];
}
console.log(JSON.stringify(out));
"""

TITLE_CASES = {
    "Proposition 2: Increases Funding": ["Proposition 2", "Increases Funding"],
    "Prop. 50: Elections": ["Prop. 50", "Elections"],
    "Measure A: Roads": ["Measure A", "Roads"],
    "Measure 114: Firearms": ["Measure 114", "Firearms"],
    "Amendment 4: Limits Government": ["Amendment 4", "Limits Government"],
    "Amendment 4 - Limits Government": ["Amendment 4", "Limits Government"],
    "Issue 1 Establishes a Right": ["Issue 1", "Establishes a Right"],
    "Question 2: Funds Schools": ["Question 2", "Funds Schools"],
    "Initiative 82: Wages": ["Initiative 82", "Wages"],
    "Initiative Measure No. 2117: Concerns Carbon":
        ["Initiative Measure No. 2117", "Concerns Carbon"],
    "Referendum 1: Repeals a Law": ["Referendum 1", "Repeals a Law"],
    "Constitutional Amendment 3: Judges":
        ["Constitutional Amendment 3", "Judges"],
    "Charter Amendment B: Mayor": ["Charter Amendment B", "Mayor"],
    "Measure ULT: Parcel tax": ["Measure ULT", "Parcel tax"],
    "Amendment A - Lowers taxes": ["Amendment A", "Lowers taxes"],
    "Measure A Roads": [None, "Measure A Roads"],
    "Proposition 2 — Water Bonds": ["Proposition 2", "Water Bonds"],
    "Fake Congressional Measure": [None, "Fake Congressional Measure"],
    "Measure to Fund Parks": [None, "Measure to Fund Parks"],
}


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class TitlePartsTest(unittest.TestCase):
    def test_designations(self):
        out = subprocess.run(
            ["node", "-e", TITLE_PARTS_HARNESS, str(STATIC_DIR / "app.js"),
             json.dumps(list(TITLE_CASES))],
            check=True, capture_output=True, text=True).stdout
        self.assertEqual(json.loads(out), TITLE_CASES)


# Runs app.js's videoNodes under node with a minimal stand-in for the
# DOM, with and without a video, and taps the full-screen button with
# each browser's fullscreen API (iPhone Safari has only
# webkitEnterFullscreen on a <video>).
FULLSCREEN_HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
function node(tag) {
  return {
    tag, attrs: {}, children: [], listeners: {}, textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    addEventListener(t, f) { this.listeners[t] = f; },
    set innerHTML(v) { this.html = v; },
  };
}
globalThis.document = {
  createElement: node,
  createTextNode: (text) => ({ tag: "#text", text, children: [] }),
};
const helpers = src.slice(src.indexOf("function el("),
                          src.indexOf("// -- map drawing"));
const video = src.slice(
  src.indexOf("// -- the video and its full-screen button"),
  src.indexOf("async function renderContest"));
eval(helpers + video + "; globalThis.videoNodes = videoNodes;");
function find(n, pred) {
  if (pred(n)) return n;
  for (const c of n.children || []) {
    const hit = find(c, pred);
    if (hit) return hit;
  }
  return null;
}
const text = (n) => n.tag === "#text" ? n.text :
  (n.textContent || "") + (n.children || []).map(text).join("");
const out = { without: videoNodes({ video_url: null }).length };
for (const api of ["iphone", "standard"]) {
  const nodes = videoNodes({ video_url: "/v/abc/1/video.mp4",
                             poster_url: "/v/abc/1/poster.jpg" });
  const root = { children: nodes };
  const v = find(root, (n) => n.tag === "video");
  const btn = find(root, (n) => n.tag === "button");
  const calls = [];
  if (api === "iphone") {
    v.webkitEnterFullscreen = () => calls.push("webkitEnterFullscreen");
  } else {
    v.requestFullscreen = () => { calls.push("requestFullscreen");
                                  return Promise.resolve(); };
    v.webkitEnterFullscreen = () => calls.push("webkitEnterFullscreen");
  }
  btn.listeners.click();
  out[api] = { count: nodes.length, order: nodes.map((n) => n.attrs.class),
               label: text(btn).trim(), cls: btn.attrs.class, calls };
}
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class FullscreenButtonTest(unittest.TestCase):
    def test_button_only_with_a_video(self):
        out = json.loads(subprocess.run(
            ["node", "-e", FULLSCREEN_HARNESS, str(STATIC_DIR / "app.js")],
            check=True, capture_output=True, text=True).stdout)
        self.assertEqual(out["without"], 0)
        for api, call in (("iphone", "webkitEnterFullscreen"),
                          ("standard", "requestFullscreen")):
            with self.subTest(api):
                got = out[api]
                # The button sits directly under the video's frame.
                self.assertEqual(got["order"], ["video-frame has-fullscreen",
                                                "fullscreen-row"])
                self.assertEqual(got["label"], "Full screen")
                self.assertIn("btn", got["cls"].split())
                self.assertEqual(got["calls"], [call])

    def test_tap_target(self):
        css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
        m = re.search(r"\.fullscreen-btn \{[^}]*min-height: (\d+)px", css)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 44)
