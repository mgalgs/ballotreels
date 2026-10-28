"""The state page's crash course (app.js crashCourseNodes): the video at
the top, with a chip per measure, once one has been made; nothing at all
before then, so the page is as it always was."""

import json
import shutil
import subprocess
import unittest

from ballotreels.site.server import STATIC_DIR

COURSE = {
    "id": "ut-2026-11-03-crash-course", "measures": 2, "status": "cached",
    "video_url": "/v/0123456789abcdef/7/video.mp4",
    "poster_url": "/v/0123456789abcdef/7/poster.jpg",
    "chapters": [
        {"start": 2.0, "title": "Constitutional Amendment A: Publication Amendments"},
        {"start": 19.034, "title": "Constitutional Amendment B: Statewide Initiatives"},
    ],
}

HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const course = JSON.parse(process.argv[2]);
function node(tag) {
  return {
    tag, attrs: {}, children: [], listeners: {}, textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    addEventListener(t, f) {
      (this.listeners[t] = this.listeners[t] || []).push(f);
    },
    querySelector(sel) { return all(this, (n) => n.tag === sel)[0]; },
  };
}
function all(n, pred, out = []) {
  if (pred(n)) out.push(n);
  for (const c of n.children || []) all(c, pred, out);
  return out;
}
globalThis.document = {
  createElement: node,
  createTextNode: (text) => ({ tag: "#text", text, children: [] }),
};
globalThis.localStorage = { getItem: () => null, setItem() {} };
URL.createObjectURL = () => "blob:0";
const helpers = src.slice(src.indexOf("function el("),
                          src.indexOf("// -- map drawing"));
const part = src.slice(src.indexOf("// -- the video and its full-screen"),
                       src.indexOf("async function renderContest"));
eval(helpers + part + "; globalThis.crashCourseNodes = crashCourseNodes;");
const text = (n) => n.tag === "#text" ? n.text :
  (n.textContent || "") + (n.children || []).map(text).join("");
const nodes = crashCourseNodes(course);
const out = {
  count: nodes.length,
  heading: all({ children: nodes }, (n) => n.tag === "h2").map(text),
  videos: all({ children: nodes }, (n) => n.tag === "video")
    .map((v) => v.attrs.src),
  chips: all({ children: nodes }, (n) => n.tag === "button" &&
             n.attrs.class === "chapter-chip").map((c) => text(c.children[1])),
  none: crashCourseNodes(null).length,
  notYet: crashCourseNodes({ ...course, status: "none", video_url: null,
                             chapters: [] }).length,
};
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class CrashCourseNodesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = json.loads(subprocess.run(
            ["node", "-e", HARNESS, str(STATIC_DIR / "app.js"),
             json.dumps(COURSE)],
            check=True, capture_output=True, text=True).stdout)

    def test_the_video_with_a_chip_per_measure(self):
        self.assertEqual(self.out["count"], 1)
        self.assertEqual(self.out["heading"], ["Every measure in one video"])
        self.assertEqual(self.out["videos"], [COURSE["video_url"]])
        self.assertEqual(self.out["chips"],
                         [c["title"] for c in COURSE["chapters"]])

    def test_nothing_until_one_is_made(self):
        self.assertEqual(self.out["none"], 0)
        self.assertEqual(self.out["notYet"], 0)


if __name__ == "__main__":
    unittest.main()
