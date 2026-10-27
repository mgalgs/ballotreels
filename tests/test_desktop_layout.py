"""The contest page's layout in a real browser: on a wide screen the
video takes the viewport's height beside the text; on a phone or a
tablet in portrait it stays above it, as it always was."""

import json
import shutil
import subprocess
import unittest

from ballotreels.index import key_for
from ballotreels.queue import hash_for_key

from .test_serve_public import ServerTestCase

CHROMIUM = shutil.which("chromium") or shutil.which("chromium-browser")

# Drives headless Chromium over --remote-debugging-pipe (fd 3 in, fd 4
# out, NUL-separated JSON), so no port or WebSocket is needed. For each
# viewport it loads the page and prints the frame's and the sources
# heading's boxes, then the frame's top once the page is scrolled.
LAYOUT_HARNESS = r"""
const { spawn } = require("child_process");
const [chromium, url, sizes] = process.argv.slice(1);
const proc = spawn(chromium, ["--headless=new", "--disable-gpu",
  "--disable-dev-shm-usage", "--hide-scrollbars",
  "--remote-debugging-pipe", "about:blank"],
  { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
let id = 0, buf = "";
const waiting = new Map();
proc.stdio[4].on("data", (chunk) => {
  buf += chunk;
  let i;
  while ((i = buf.indexOf("\0")) >= 0) {
    const msg = JSON.parse(buf.slice(0, i));
    buf = buf.slice(i + 1);
    if (msg.id && waiting.has(msg.id)) {
      waiting.get(msg.id)(msg);
      waiting.delete(msg.id);
    }
  }
});
function send(method, params, sessionId) {
  const msg = { id: ++id, method, params: params || {} };
  if (sessionId) msg.sessionId = sessionId;
  proc.stdio[3].write(JSON.stringify(msg) + "\0");
  return new Promise((resolve, reject) => waiting.set(msg.id, (m) =>
    m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result)));
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const MEASURE = `(() => {
  const box = (sel) => {
    const n = document.querySelector(sel);
    if (!n) return null;
    const r = n.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom,
             width: r.width, height: r.height };
  };
  return JSON.stringify({ frame: box(".video-frame"),
                          sources: box(".contest-rest .section-title"),
                          full: box(".fullscreen-btn") });
})()`;
(async () => {
  const out = {};
  for (const size of JSON.parse(sizes)) {
    const [w, h] = size.split("x").map(Number);
    const { targetId } = await send("Target.createTarget",
                                    { url: "about:blank" });
    const { sessionId } = await send("Target.attachToTarget",
                                     { targetId, flatten: true });
    await send("Emulation.setDeviceMetricsOverride",
      { width: w, height: h, deviceScaleFactor: 1, mobile: false },
      sessionId);
    await send("Page.navigate", { url }, sessionId);
    const evaluate = async (expression) => (await send("Runtime.evaluate",
      { expression, awaitPromise: true, returnByValue: true },
      sessionId)).result.value;
    for (let i = 0; i < 100; i++) {
      if (await evaluate(`!!document.querySelector(".contest-rest")`)) break;
      await sleep(50);
    }
    await evaluate(`document.fonts.ready.then(() => new Promise(
      (r) => requestAnimationFrame(() => requestAnimationFrame(r))))`);
    const loaded = JSON.parse(await evaluate(MEASURE));
    await evaluate(`window.scrollTo(0, 300)`);
    await sleep(100);
    const scrolled = JSON.parse(await evaluate(MEASURE));
    out[size] = { loaded, scrolled,
                  scrollY: await evaluate(`window.scrollY`) };
    await send("Target.closeTarget", { targetId });
  }
  console.log(JSON.stringify(out));
  proc.kill();
})().catch((e) => { console.error(e); proc.kill(); process.exit(1); });
"""

WIDE = ("1440x900", "1920x1080", "1024x768")
# A phone, and tablets in portrait (an iPad, a 12.9" iPad Pro).
NARROW = ("390x844", "820x1180", "1024x1366")


@unittest.skipUnless(CHROMIUM and shutil.which("node"),
                     "chromium or node is not on PATH")
class ContestLayoutTest(ServerTestCase):
    def setUp(self):
        super().setUp()
        # A video for the fixture's Prop 90: the file need not exist,
        # the frame is laid out the same. Enough sources that the text
        # beside it is longer than the video, so there is scrolling to
        # stay put through.
        state, entry = self.deps.contest("ca-2026-11-03-prop-90")
        key = key_for(state.index.election.id, entry, self.deps.standard)
        self.deps.queue.create_job(key)
        claimed = self.deps.queue.claim("w1")
        h = hash_for_key(key)
        self.deps.queue.complete(
            claimed["id"], claimed["claim"],
            video=(key, "local",
                   {"video": f"/v/{h}/{claimed['id']}/video.mp4"},
                   [{"publisher": f"Publisher {i}",
                     "url": f"https://example.test/{i}"}
                    for i in range(20)]))
        _, body = self.get(self.public_port,
                           "/api/contest/ca-2026-11-03-prop-90")
        path = json.loads(body)["path"]
        out = subprocess.run(
            ["node", "-e", LAYOUT_HARNESS, CHROMIUM,
             f"http://127.0.0.1:{self.public_port}{path}",
             json.dumps(WIDE + NARROW)],
            check=True, capture_output=True, text=True, timeout=120).stdout
        self.layout = json.loads(out)

    def test_layouts(self):
        for size in WIDE:
            with self.subTest(size):
                w, h = map(int, size.split("x"))
                got = self.layout[size]
                frame, sources = got["loaded"]["frame"], got["loaded"]["sources"]
                # As tall as the viewport allows, below the header, with
                # a little paper under it; 9:16.
                self.assertLessEqual(frame["bottom"], h)
                self.assertGreaterEqual(frame["bottom"], h - 40)
                self.assertLess(frame["top"], 130)
                self.assertAlmostEqual(frame["width"] / frame["height"],
                                       9 / 16, delta=0.01)
                # The sources beside it, on screen without scrolling.
                self.assertGreater(sources["left"], frame["right"])
                self.assertLess(sources["bottom"], h)
                full = got["loaded"]["full"]
                self.assertGreater(full["left"], frame["right"])
                # The video stays put while the text scrolls.
                self.assertEqual(got["scrollY"], 300)
                self.assertEqual(got["scrolled"]["frame"]["top"], 16)

        for size in NARROW:
            with self.subTest(size):
                w, h = map(int, size.split("x"))
                got = self.layout[size]["loaded"]
                frame, sources = got["frame"], got["sources"]
                # Stacked: the full-screen button under the video, the
                # sources under that, all in the one centred column.
                self.assertGreater(got["full"]["top"], frame["bottom"])
                self.assertGreater(sources["top"], got["full"]["bottom"])
                self.assertLessEqual(abs((frame["left"] + frame["right"]) / 2
                                         - w / 2), 1)
                # Frame and button both on screen without scrolling.
                self.assertLessEqual(got["full"]["bottom"], h)


if __name__ == "__main__":
    unittest.main()
