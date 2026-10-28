"""The district map on a phone: each district told apart by its own fill
pattern, line dash and letter, all in the one map grey (STANDARD rule
4.1); a muted base map; zoom controls a finger can hit."""

import json
import re
import shutil
import subprocess
import unittest

from .helpers import REPO

STATIC_DIR = REPO / "ballotreels" / "site" / "static"

# Runs app.js's SVG fallback map under node with a minimal stand-in for
# the DOM, over a zip split three ways, and reports what it drew.
FALLBACK_HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
function node(tag) {
  return {
    tag, attrs: {}, children: [], listeners: {}, style: {}, textContent: "",
    setAttribute(k, v) { this.attrs[k] = String(v); },
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(c) { this.children.unshift(c); return c; },
    addEventListener(t, f) { this.listeners[t] = f; },
  };
}
globalThis.document = { createElementNS: (ns, tag) => node(tag) };
const consts = src.slice(src.indexOf("const MAP_COLOR"),
                         src.indexOf("const app ="));
const drawing = src.slice(src.indexOf("// -- map drawing"),
                          src.indexOf("// -- routes"));
eval(consts + drawing +
     "; globalThis.drawFallbackSvg = drawFallbackSvg;" +
     " globalThis.MAP_COLOR = MAP_COLOR;");
const square = (x0, y0, x1, y1) =>
  [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]];
const fc = { type: "FeatureCollection", features: [
  { properties: { role: "district", ocd_id: "d1" },
    geometry: { coordinates: square(-1, 40, 0, 41) } },
  { properties: { role: "district", ocd_id: "d2" },
    geometry: { coordinates: square(0, 40, 1, 41) } },
  { properties: { role: "district", ocd_id: "d3" },
    geometry: { coordinates: square(-1, 39, 1, 40) } },
  { properties: { role: "zip" },
    geometry: { coordinates: square(-0.5, 39.5, 0.5, 40.5) } },
] };
const container = node("div");
const tapped = [];
drawFallbackSvg(container, fc, (id) => tapped.push(id),
                { d1: "A", d2: "B", d3: "C" });
const svg = container.children[0];
const all = [];
(function walk(n) { all.push(n); (n.children || []).forEach(walk); })(svg);
const defs = svg.children.find((c) => c.tag === "defs");
const patterns = {};
for (const p of defs.children) {
  // What a pattern looks like: its transform and its marks.
  patterns[p.attrs.id] = JSON.stringify([p.attrs.patternTransform || "",
    p.children.map((c) => [c.tag, c.attrs])]);
}
const polys = svg.children.filter((c) => c.tag === "polygon");
for (const p of polys) if (p.listeners.click) p.listeners.click();
const labels = svg.children.filter((c) => c.tag === "g");
console.log(JSON.stringify({
  mapColor: MAP_COLOR,
  paints: all.flatMap((n) => ["fill", "stroke"].map((k) => n.attrs[k]))
    .filter((v) => v !== undefined),
  patterns,
  polys: polys.map((p) => ({ fill: p.attrs.fill,
                             dash: p.attrs["stroke-dasharray"] || null,
                             points: p.attrs.points })),
  tapped,
  labels: labels.map((g) => ({
    letter: g.children.find((c) => c.tag === "text").textContent,
    x: Number(g.children[0].attrs.cx), y: Number(g.children[0].attrs.cy),
  })),
}));
"""


def _inside(x, y, points):
    """Even-odd ray cast over one ring of "x,y x,y ..." svg points."""
    ring = [tuple(map(float, p.split(","))) for p in points.split()]
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        (xi, yi), (xj, yj) = ring[i], ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class FallbackMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = json.loads(subprocess.run(
            ["node", "-e", FALLBACK_HARNESS, str(STATIC_DIR / "app.js")],
            check=True, capture_output=True, text=True).stdout)

    def test_one_grey_only(self):
        # Every fill and stroke is the map grey, none, or a pattern drawn
        # in it: no hue anywhere (STANDARD rule 4.1).
        for paint in self.out["paints"]:
            with self.subTest(paint=paint):
                self.assertTrue(
                    paint in (self.out["mapColor"], "none")
                    or re.fullmatch(r"url\(#district-pattern-\d+\)", paint),
                    paint)

    def test_each_district_its_own_pattern(self):
        districts = self.out["polys"][:3]
        fills = [p["fill"] for p in districts]
        self.assertEqual(len(set(fills)), 3)
        looks = []
        for fill in fills:
            pattern_id = re.fullmatch(r"url\(#(.+)\)", fill).group(1)
            self.assertIn(pattern_id, self.out["patterns"])
            looks.append(self.out["patterns"][pattern_id])
        # Told apart by their look, not only by their ids.
        self.assertEqual(len(set(looks)), 3)
        self.assertEqual(len(set(self.out["patterns"].values())),
                         len(self.out["patterns"]))
        # And by their lines' dashes, as before.
        self.assertEqual(len({p["dash"] for p in districts}), 3)

    def test_zip_outline_on_top_unfilled(self):
        zip_poly = self.out["polys"][-1]
        self.assertEqual(zip_poly["fill"], "none")

    def test_letters_inside_their_districts(self):
        polys = self.out["polys"][:3]
        letters = [label["letter"] for label in self.out["labels"]]
        self.assertEqual(letters, ["A", "B", "C"])
        for label, poly in zip(self.out["labels"], polys):
            with self.subTest(letter=label["letter"]):
                self.assertTrue(_inside(label["x"], label["y"],
                                        poly["points"]))

    def test_tap_selects(self):
        self.assertEqual(self.out["tapped"], ["d1", "d2", "d3"])


class MapControlsTest(unittest.TestCase):
    def setUp(self):
        self.app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")

    def test_zoom_buttons_touch_sized(self):
        m = re.search(r"\.leaflet-control-zoom\.leaflet-bar a \{([^}]*)\}",
                      self.css)
        self.assertIsNotNone(m)
        for prop in ("width", "height"):
            size = re.search(rf"(?<![-\w]){prop}: (\d+)px", m.group(1))
            self.assertIsNotNone(size, prop)
            self.assertGreaterEqual(int(size.group(1)), 44)

    def test_zoom_hint_and_no_scroll_trap(self):
        self.assertIn("Drag to move · + − to zoom", self.app_js)
        self.assertIn("mapHint().addTo(map)", self.app_js)
        self.assertIn("scrollWheelZoom: false", self.app_js)

    def test_base_map_muted_same_tiles(self):
        m = re.search(r"\.leaflet-tile-pane \{([^}]*)\}", self.css)
        self.assertIn("grayscale(1)", m.group(1))
        opacity = float(re.search(r"opacity: ([\d.]+)", m.group(1)).group(1))
        self.assertLessEqual(opacity, 0.7)
        # Still the one tile provider: no new third-party requests.
        self.assertEqual(re.findall(r"https://[a-z.]*tile[a-z.]*/",
                                    self.app_js),
                         ["https://tile.openstreetmap.org/"])

    def test_leaflet_districts_patterned(self):
        self.assertIn("fillColor: isZip ? MAP_COLOR : districtFill(n)",
                      self.app_js)
        self.assertIn("overlay.insertBefore(patternDefs()", self.app_js)


if __name__ == "__main__":
    unittest.main()
