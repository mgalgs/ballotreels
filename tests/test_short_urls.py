"""Short, shareable page paths (/ut, /ut/2026/amendment-a) and the
link-preview tags in their HTML; old links; unknown paths as 404s."""

import argparse
import http.client
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from html.parser import HTMLParser
from pathlib import Path

import ballotreels.site.config as site_config
from ballotreels.index import key_for
from ballotreels.site import pages
from ballotreels.site.config import load_config
from ballotreels.site.server import build_deps, make_servers
from ballotreels.standard import judgment_word_pattern, load_standard

from . import geo_fixtures
from .helpers import REPO
from .test_multistate import _write_election
from .test_serve_public import _make_config

STATIC_DIR = REPO / "ballotreels" / "site" / "static"

# A title with every character HTML needs escaped (and TOML's own
# escaping of the quotes, as it would sit in contests.toml).
TRICKY_TOML = r'Proposition 9: \"Fair\" <Rules> & More.'
TRICKY = 'Proposition 9: "Fair" <Rules> & More'


class _HeadTags(HTMLParser):
    """The <title> text and every <meta>/<link> tag's attributes."""

    def __init__(self):
        super().__init__()
        self.title = None
        self.meta = {}
        self.links = {}
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
            self.title = ""
        elif tag == "meta" and "content" in attrs:
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.meta[key] = attrs["content"]
        elif tag == "link" and "rel" in attrs:
            self.links[attrs["rel"]] = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def head_tags(html_bytes):
    parser = _HeadTags()
    parser.feed(html_bytes.decode("utf-8"))
    return parser


class ShortUrlTestCase(unittest.TestCase):
    config_overrides: dict = {}

    def setUp(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = tmp / "data"
        _write_election(self.root, "ca-2026-11-03", "ca", [
            ("prop-3", "", "Proposition 3: Fake California Measure."),
            ("prop-9", "", TRICKY_TOML),
            ("cd-1", "/cd:1", "Fake California District Measure")])
        _write_election(self.root, "ut-2026-11-03", "ut", [
            ("amendment-a", "", "Constitutional Amendment A: Fake")])
        _write_election(self.root, "tx-2026-11-03", "tx", [])
        old_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = self.root
        self.addCleanup(setattr, site_config, "DATA_ROOT", old_root)
        data_dir = tmp / "var"
        geo_fixtures.build_fixture_geo(data_dir)
        self.deps = build_deps(
            _make_config(data_dir, election=None, **self.config_overrides),
            warn=lambda m: None)
        self.addCleanup(self.deps.queue.close)
        self.public, self.private = make_servers(self.deps)
        for srv in (self.public, self.private):
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        for srv in (self.public, self.private):
            srv.shutdown()
            srv.server_close()

    def request(self, path, method="GET", headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.public.server_address[1], timeout=5)
        conn.request(method, path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def page(self, path, status=200):
        resp, body = self.request(path)
        self.assertEqual(resp.status, status, path)
        self.assertIn("text/html", resp.getheader("Content-Type"))
        self.assertIn(b"/static/app.js", body)
        return head_tags(body), body

    def finish_video(self, contest_id, urls):
        state, entry = self.deps.contest(contest_id)
        key = key_for(state.index.election.id, entry, self.deps.standard)
        self.deps.queue.create_job(key)
        claimed = self.deps.queue.claim("w1")
        self.assertTrue(self.deps.queue.complete(
            claimed["id"], claimed["claim"], video=(key, "local", urls, [])))


class MeasurePageTest(ShortUrlTestCase):
    def test_measure_page_tags(self):
        tags, _ = self.page("/ut/2026/amendment-a")
        title = "Utah Constitutional Amendment A: Fake, explained in 60 seconds"
        self.assertEqual(tags.title, title)
        self.assertEqual(tags.meta["og:title"], title)
        self.assertEqual(tags.meta["twitter:title"], title)
        url = "https://ballotreels.org/ut/2026/amendment-a"
        self.assertEqual(tags.meta["og:url"], url)
        self.assertEqual(tags.links["canonical"], url)
        self.assertEqual(tags.meta["og:type"], "website")
        self.assertEqual(tags.meta["og:site_name"], "ballotreels")
        self.assertEqual(tags.meta["twitter:card"], "summary_large_image")
        # No video yet: the site-wide card.
        image = "https://ballotreels.org/static/og-card.png"
        self.assertEqual(tags.meta["og:image"], image)
        self.assertEqual(tags.meta["twitter:image"], image)
        description = tags.meta["description"]
        self.assertEqual(tags.meta["og:description"], description)
        self.assertEqual(tags.meta["twitter:description"], description)
        self.assertIn("even-handed", description)
        self.assertIn("every claim sourced", description)
        self.assertIn("Utah Constitutional Amendment A: Fake", description)

    def test_the_default_image_exists(self):
        resp, body = self.request("/static/og-card.png")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "image/png")
        # PNG header: width and height at bytes 16-24.
        self.assertEqual(int.from_bytes(body[16:20], "big"), 1200)
        self.assertEqual(int.from_bytes(body[20:24], "big"), 630)

    def test_trailing_period_dropped_before_the_comma(self):
        tags, _ = self.page("/ca/2026/prop-3")
        self.assertEqual(tags.title, "California Proposition 3: Fake "
                                     "California Measure, explained in 60 "
                                     "seconds")

    def test_poster_is_the_image_once_there_is_a_video(self):
        self.finish_video("ut-2026-11-03-amendment-a",
                          {"video": "/v/abc/1/video.mp4",
                           "poster": "/v/abc/1/poster.jpg"})
        tags, _ = self.page("/ut/2026/amendment-a")
        self.assertEqual(tags.meta["og:image"],
                         "https://ballotreels.org/v/abc/1/poster.jpg")
        self.assertNotIn("og:image:width", tags.meta)
        # A CDN's poster URL is already absolute.
        self.finish_video("ca-2026-11-03-prop-3",
                          {"video": "https://cdn.test/x/video.mp4",
                           "poster": "https://cdn.test/x/poster.jpg"})
        tags, _ = self.page("/ca/2026/prop-3")
        self.assertEqual(tags.meta["twitter:image"],
                         "https://cdn.test/x/poster.jpg")

    def test_title_is_escaped(self):
        tags, raw = self.page("/ca/2026/prop-9")
        self.assertEqual(tags.title,
                         f"California {TRICKY}, explained in 60 seconds")
        self.assertEqual(tags.meta["og:title"], tags.title)
        self.assertIn(TRICKY, tags.meta["description"])
        head = raw.decode("utf-8").split("</head>")[0]
        self.assertNotIn("<Rules>", head)
        self.assertNotIn('"Fair"', head)
        self.assertIn("&quot;Fair&quot; &lt;Rules&gt; &amp; More", head)

    def test_copy_is_neutral(self):
        pattern = judgment_word_pattern(load_standard().judgment_words)
        for path in ("/", "/ut", "/tx", "/ut/2026/amendment-a"):
            with self.subTest(path):
                tags, _ = self.page(path)
                for text in (tags.title, tags.meta["description"]):
                    self.assertEqual(pattern.findall(text), [])

    def test_head_request(self):
        resp, body = self.request("/ut/2026/amendment-a", method="HEAD")
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, b"")


class StatePageTest(ShortUrlTestCase):
    def test_state_page_tags(self):
        tags, _ = self.page("/ut")
        self.assertEqual(tags.title,
                         "Utah statewide measures, explained in 60 seconds")
        self.assertEqual(tags.meta["og:url"], "https://ballotreels.org/ut")
        # its own card: the flag inside the state
        self.assertEqual(tags.meta["og:image"],
                         "https://ballotreels.org/static/og/ut.jpg")
        self.assertEqual(tags.meta["og:image:width"], "1200")
        self.assertIn("Utah's November 3, 2026 ballot",
                      tags.meta["description"])
        resp, _ = self.request("/static/og/ut.jpg")
        self.assertEqual(resp.status, 200)

    def test_every_built_state_has_a_card(self):
        for counties in (REPO / "var" / "geo").glob("*/counties.json"):
            abbr = counties.parent.name
            with self.subTest(abbr):
                self.assertTrue(
                    (STATIC_DIR / pages.state_card_path(abbr)).is_file())

    def test_state_page_by_year(self):
        tags, _ = self.page("/ut/2026")
        self.assertEqual(tags.meta["og:url"],
                         "https://ballotreels.org/ut/2026")
        self.page("/ut/2025", status=404)

    def test_state_with_nothing_on_the_ballot(self):
        tags, _ = self.page("/tx")
        self.assertIn("no statewide measures", tags.meta["description"])

    def test_home_page_tags(self):
        tags, _ = self.page("/")
        self.assertEqual(tags.meta["og:url"], "https://ballotreels.org/")
        self.assertEqual(tags.meta["og:title"],
                         "ballotreels: your ballot, explained")
        self.assertIn("twitter:card", tags.meta)

    def test_paths_in_the_api(self):
        resp, body = self.request("/api/state/ca")
        state = json.loads(body)
        self.assertEqual(state["year"], "2026")
        self.assertEqual([c["path"] for c in state["levels"][0]["contests"]],
                         ["/ca/2026/prop-3", "/ca/2026/prop-9"])
        resp, body = self.request("/api/contest/ca/2026/prop-3")
        self.assertEqual(resp.status, 200)
        detail = json.loads(body)
        self.assertEqual(detail["id"], "ca-2026-11-03-prop-3")
        self.assertEqual(detail["path"], "/ca/2026/prop-3")
        resp, body = self.request("/api/contest/ca-2026-11-03-prop-3")
        self.assertEqual(json.loads(body)["path"], "/ca/2026/prop-3")
        for path in ("/api/contest/ca/2025/prop-3",
                     "/api/contest/ut/2026/prop-3"):
            with self.subTest(path):
                resp, _ = self.request(path)
                self.assertEqual(resp.status, 404)


class OldLinksTest(ShortUrlTestCase):
    def assertRedirect(self, path, location):
        resp, _ = self.request(path)
        self.assertEqual(resp.status, 301, path)
        self.assertEqual(resp.getheader("Location"), location)

    def test_old_state_links_redirect(self):
        self.assertRedirect("/state/ut", "/ut")
        self.assertRedirect("/state/tx", "/tx")
        # A state not served: the app's "We don't cover ... yet", as a 404.
        self.page("/state/fl", status=404)

    def test_case_and_trailing_slash(self):
        self.assertRedirect("/UT", "/ut")
        self.assertRedirect("/ut/", "/ut")
        self.assertRedirect("/CA/2026/Prop-3/", "/ca/2026/prop-3")
        self.assertRedirect("/UT?ref=yt", "/ut?ref=yt")
        # Only to a page there is.
        self.page("/FL", status=404)

    def test_hash_routes_still_served_by_the_root(self):
        # #/contest/<id>, #/zip/..., #/ballot?... never reach the
        # server: the root serves the app, which routes them.
        self.page("/")


class UnknownPathTest(ShortUrlTestCase):
    def test_unknown_paths_404_with_the_app(self):
        for path in ("/fl", "/zz", "/ca/2026/prop-99", "/ca/2025/prop-3",
                     "/ut/2026/prop-3", "/ca/prop-3", "/ut/2026/amendment-a/x",
                     "/state/california", "/states", "/california",
                     "/ut/26", "/index.php"):
            with self.subTest(path):
                tags, _ = self.page(path, status=404)
                self.assertEqual(tags.meta["robots"], "noindex")
                self.assertNotIn("canonical", tags.links)

    def test_reserved_prefixes_are_never_pages(self):
        for path in ("/api/ut", "/api/ca/2026/prop-3", "/static/ut",
                     "/v/ut", "/admin", "/admin/ut", "/worker/claim"):
            with self.subTest(path):
                resp, body = self.request(path)
                self.assertEqual(resp.status, 404)
                self.assertEqual(resp.getheader("Content-Type"),
                                 "application/json")
                self.assertEqual(json.loads(body), {"error": "not found"})
        resp, _ = self.request("/api/state/ut")
        self.assertEqual(resp.status, 200)


class SiteUrlFromConfigTest(ShortUrlTestCase):
    config_overrides = {"site_url": "https://staging.example"}

    def test_base_url_from_config_not_host(self):
        resp, body = self.request("/ut/2026/amendment-a",
                                  headers={"Host": "evil.test"})
        tags = head_tags(body)
        self.assertEqual(tags.meta["og:url"],
                         "https://staging.example/ut/2026/amendment-a")
        self.assertEqual(tags.meta["og:image"],
                         "https://staging.example/static/og-card.png")
        self.assertNotIn(b"evil.test", body)


class SiteUrlOptionTest(unittest.TestCase):
    def args(self, **kw):
        fields = {name: None for name in (
            "data_dir", "election", "public_host", "public_port",
            "private_host", "private_port", "generate_limit",
            "generate_window", "trust_forwarded_for", "heartbeat_timeout",
            "eta_default_minutes", "max_upload_mb")}
        fields.update(kw)
        return argparse.Namespace(**fields)

    def test_default_env_and_flag(self):
        old = os.environ.pop("BALLOTREELS_SITE_URL", None)
        self.addCleanup(lambda: old is None or os.environ.__setitem__(
            "BALLOTREELS_SITE_URL", old))
        self.assertEqual(load_config(self.args()).site_url,
                         "https://ballotreels.org")
        os.environ["BALLOTREELS_SITE_URL"] = "https://env.example/"
        try:
            self.assertEqual(load_config(self.args()).site_url,
                             "https://env.example")
            self.assertEqual(
                load_config(self.args(site_url="https://flag.example"))
                .site_url, "https://flag.example")
        finally:
            del os.environ["BALLOTREELS_SITE_URL"]


# Runs app.js's router under node with its pages stubbed, printing the
# page each URL routes to.
ROUTE_HARNESS = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const start = src.indexOf("// The page's route:");
const end = src.indexOf("function renderHome");
const calls = [];
let location;
const history = { replaceState: (s, t, href) => { location.replaced = href; },
                  pushState: () => {} };
const app = {};
const window = { scrollTo() {} };
const document = { addEventListener() {} };
const notice = () => ({});
const linkButton = () => ({});
app.appendChild = () => calls.push(["notFound"]);
const renderHome = () => calls.push(["home"]);
const renderState = (...a) => calls.push(["state", ...a]);
const renderContest = (...a) => calls.push(["contest", ...a]);
const renderZip = (...a) => calls.push(["zip", ...a]);
const renderBallot = (...a) => calls.push(["ballot", ...a]);
const renderZipBallot = (...a) => calls.push(["zipBallot", ...a]);
eval(src.slice(start, end));
const out = {};
for (const url of JSON.parse(process.argv[2])) {
  const u = new URL(url, "https://ballotreels.org");
  location = { pathname: u.pathname, search: u.search, hash: u.hash,
               href: u.href };
  calls.length = 0;
  route();
  out[url] = { call: calls[0], replaced: location.replaced || null };
}
console.log(JSON.stringify(out));
"""

ROUTES = {
    "/": ["home"],
    "/#/": ["home"],
    "/ut": ["state", "ut", None, False],
    "/ut/2026": ["state", "ut", "2026", False],
    "/ut/2026/amendment-a": ["contest", "/api/contest/ut/2026/amendment-a"],
    "/state/ut": ["state", "ut", None, True],
    "/#/state/ut": ["state", "ut", None, True],
    "/#/contest/ut-2026-11-03-amendment-a":
        ["contest", "/api/contest/ut-2026-11-03-amendment-a"],
    "/ut#/contest/ut-2026-11-03-amendment-a":
        ["contest", "/api/contest/ut-2026-11-03-amendment-a"],
    "/#/zip/84101": ["zip", "84101"],
    # the old street-address page: zips are the only lookup
    "/#/address": ["home"],
    "/#/ballot?d=a&d=b": ["ballot", ["a", "b"], []],
    # a zip's cities and school districts that cover only part of it
    "/#/ballot?d=a&d=p1&p=p1": ["ballot", ["a", "p1"], ["p1"]],
    # a zip's ballot by the voter's picks, and one the zip settles alone
    "/#/ballot/92071?cd=51&sldl=78":
        ["zipBallot", "92071", {"cd": "51", "sldl": "78"}],
    "/#/ballot/92064": ["zipBallot", "92064", {}],
    "/zip/84101": ["notFound"],
    "/ut/2026/amendment-a/x": ["notFound"],
}


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class AppRouterTest(unittest.TestCase):
    def test_routes(self):
        out = json.loads(subprocess.run(
            ["node", "-e", ROUTE_HARNESS, str(STATIC_DIR / "app.js"),
             json.dumps(list(ROUTES))],
            check=True, capture_output=True, text=True).stdout)
        for url, want in ROUTES.items():
            with self.subTest(url):
                self.assertEqual(out[url]["call"], want)
        # The home page reached by an old "#/" shows as "/".
        self.assertEqual(out["/#/"]["replaced"], "/")
        self.assertEqual(out["/#/address"]["replaced"], "/")

    def test_old_links_show_the_short_path(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        # A contest page, however reached, shows its short path; an old
        # state link shows /<st>; cards link to the short path.
        for needle in ("showPath(body.path);",
                       "if (old) showPath(`/${body.state}`);",
                       'el("a", { class: "box contest", href: contest.path }',
                       "go(contest.path);",
                       'window.addEventListener("popstate", onHistory);'):
            self.assertIn(needle, app_js)
        # Every navigation goes through go(), not the hash.
        self.assertIsNone(re.search(
            r"location\.hash\s*=[^=]|location\.replace\(", app_js))


if __name__ == "__main__":
    unittest.main()
