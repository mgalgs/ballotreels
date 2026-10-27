"""The contest page's chapter chips (app.js chapterNodes): one per
section, in order, labelled with its heading; a tap seeks the video and
plays; the chips look alike for either side (STANDARD rule 7.4), and the
only one marked is the one the playhead is in. The video also gets the
chapters as a WebVTT kind="chapters" track. A video with no chapters
(made before they were recorded) gets neither."""

import json
import re
import shutil
import subprocess
import unittest

from ballotreels.site.server import STATIC_DIR

CHAPTERS = [
    {"start": 0, "title": "Proposition 2"},
    {"start": 3.834, "title": "Why a rainy day fund"},
    {"start": 38.4, "title": "Why some vote no"},
    {"start": 45.234, "title": "Why some vote yes"},
    {"start": 52.067, "title": "What your vote means"},
]

HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const chapters = JSON.parse(process.argv[2]);
function node(tag) {
  return {
    tag, attrs: {}, children: [], listeners: {}, textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    addEventListener(t, f) {
      (this.listeners[t] = this.listeners[t] || []).push(f);
    },
    set innerHTML(v) { this.html = v; },
  };
}
globalThis.document = {
  createElement: node,
  createTextNode: (text) => ({ tag: "#text", text, children: [] }),
};
const blobs = {};
URL.createObjectURL = (blob) => {
  const url = `blob:${Object.keys(blobs).length}`;
  blobs[url] = blob;
  return url;
};
const helpers = src.slice(src.indexOf("function el("),
                          src.indexOf("// -- map drawing"));
const part = src.slice(src.indexOf("// -- chapters: a chip per section"),
                       src.indexOf("async function renderContest"));
eval(helpers + part + "; globalThis.chapterNodes = chapterNodes;");
function all(n, pred, out = []) {
  if (pred(n)) out.push(n);
  for (const c of n.children || []) all(c, pred, out);
  return out;
}
const text = (n) => n.tag === "#text" ? n.text :
  (n.textContent || "") + (n.children || []).map(text).join("");
function fakeVideo() {
  const v = node("video");
  v.paused = true;
  v.currentTime = 0;
  v.plays = 0;
  v.play = () => { v.plays++; v.paused = false; fire(v, "play");
                   return Promise.resolve(); };
  return v;
}
function fire(v, type) { for (const f of v.listeners[type] || []) f(); }
(async () => {
  const out = {};
  const bare = fakeVideo();
  out.without = { nodes: chapterNodes([], bare).length,
                  nullNodes: chapterNodes(undefined, bare).length,
                  tracks: bare.children.length };
  const v = fakeVideo();
  const nodes = chapterNodes(chapters, v);
  const chips = all({ children: nodes }, (n) => n.tag === "button");
  const current = () => chips.map((c) => c.attrs["aria-current"] || null);
  out.count = nodes.length;
  out.labels = chips.map((c) => text(c.children[1]));
  out.times = chips.map((c) => text(c.children[0]));
  out.attrs = chips.map((c) => ({ ...c.attrs }));
  out.before = current();
  chips[3].listeners.click[0]();
  out.seek = { t: v.currentTime, plays: v.plays };
  out.afterClick = current();
  v.currentTime = 40;
  fire(v, "timeupdate");
  out.at40 = current();
  v.paused = true;
  v.currentTime = 52.067;
  fire(v, "seeked");
  out.pausedLast = current();
  const track = v.children.find((c) => c.tag === "track");
  out.track = track && track.attrs;
  out.vtt = track && await blobs[track.attrs.src].text();
  console.log(JSON.stringify(out));
})();
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class ChapterChipsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = json.loads(subprocess.run(
            ["node", "-e", HARNESS, str(STATIC_DIR / "app.js"),
             json.dumps(CHAPTERS)],
            check=True, capture_output=True, text=True).stdout)

    def test_none_for_a_video_without_chapters(self):
        self.assertEqual(self.out["without"],
                         {"nodes": 0, "nullNodes": 0, "tracks": 0})

    def test_one_chip_per_section_in_order_with_its_heading(self):
        self.assertEqual(self.out["count"], 1)
        self.assertEqual(self.out["labels"], [c["title"] for c in CHAPTERS])
        self.assertEqual(self.out["times"],
                         ["0:00", "0:03", "0:38", "0:45", "0:52"])

    def test_every_chip_is_alike(self):
        # the same element, class and attributes for every chip: nothing
        # tells the yes side's from the no side's, or any from another
        self.assertEqual({json.dumps(a, sort_keys=True)
                          for a in self.out["attrs"]},
                         {json.dumps({"type": "button",
                                      "class": "chapter-chip"},
                                     sort_keys=True)})

    def test_a_tap_seeks_and_plays(self):
        self.assertEqual(self.out["seek"], {"t": CHAPTERS[3]["start"],
                                            "plays": 1})

    def test_only_the_chapter_playing_is_marked(self):
        self.assertEqual(self.out["before"], [None] * 5)
        self.assertEqual(self.out["afterClick"],
                         [None, None, None, "true", None])
        self.assertEqual(self.out["at40"], [None, None, "true", None, None])
        self.assertEqual(self.out["pausedLast"],
                         [None, None, None, None, "true"])

    def test_a_webvtt_chapters_track(self):
        self.assertEqual(self.out["track"]["kind"], "chapters")
        vtt = self.out["vtt"]
        self.assertTrue(vtt.startswith("WEBVTT\n\n"))
        cues = re.findall(r"(\d+)\n(\S+) --> (\S+)\n(.+)", vtt)
        self.assertEqual([c[3] for c in cues], [c["title"] for c in CHAPTERS])
        self.assertEqual(cues[0][1:3], ("00:00:00.000", "00:00:03.834"))
        self.assertEqual(cues[2][1:3], ("00:00:38.400", "00:00:45.234"))
        self.assertEqual(cues[4][1], "00:00:52.067")


class ChapterChipStyleTest(unittest.TestCase):
    def setUp(self):
        css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
        self.css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    def test_tap_target(self):
        m = re.search(r"\.chapter-chip \{[^}]*min-height: (\d+)px", self.css)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 44)

    def test_no_rule_singles_a_chip_out_but_the_one_playing(self):
        selectors = re.findall(r"([^{}]*chapter[^{}]*)\{", self.css)
        for sel in selectors:
            sel = sel.strip()
            self.assertNotRegex(sel, r":(nth|first|last)-|yes|no\b|side",
                                sel)
            if "[" in sel:
                self.assertEqual(sel, '.chapter-chip[aria-current="true"]')


if __name__ == "__main__":
    unittest.main()
