"""The site's root files (icons, manifest, robots.txt, sitemap.xml), the
head tags every page carries, and a measure video's structured data."""

import json
import re
import unittest
import xml.etree.ElementTree as ET

from ballotreels.site import pages

from .helpers import REPO
from .test_short_urls import ShortUrlTestCase

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class RootFilesTest(ShortUrlTestCase):
    def test_icons_and_manifest(self):
        for path, content_type in (
                ("/favicon.ico", "image/x-icon"),
                ("/favicon.svg", "image/svg+xml"),
                ("/apple-touch-icon.png", "image/png"),
                ("/site.webmanifest", "application/manifest+json"),
                ("/static/icon-192.png", "image/png"),
                ("/static/icon-512.png", "image/png")):
            with self.subTest(path):
                resp, body = self.request(path)
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.getheader("Content-Type"), content_type)
                self.assertTrue(body)

    def test_apple_touch_icon_is_180_square(self):
        _, body = self.request("/apple-touch-icon.png")
        self.assertEqual(int.from_bytes(body[16:20], "big"), 180)
        self.assertEqual(int.from_bytes(body[20:24], "big"), 180)

    def test_manifest_icons_exist(self):
        _, body = self.request("/site.webmanifest")
        manifest = json.loads(body)
        self.assertEqual(manifest["name"], "ballotreels")
        self.assertEqual(manifest["start_url"], "/")
        for icon in manifest["icons"]:
            with self.subTest(icon["src"]):
                resp, _ = self.request(icon["src"])
                self.assertEqual(resp.status, 200)

    def test_robots(self):
        resp, body = self.request("/robots.txt")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/plain", resp.getheader("Content-Type"))
        text = body.decode("utf-8")
        for prefix in ("/admin", "/api/", "/worker/"):
            self.assertIn(f"Disallow: {prefix}\n", text)
        self.assertIn("Sitemap: https://ballotreels.org/sitemap.xml\n", text)

    def test_sitemap_lists_the_served_pages(self):
        resp, body = self.request("/sitemap.xml")
        self.assertEqual(resp.status, 200)
        self.assertIn("application/xml", resp.getheader("Content-Type"))
        locs = [e.text for e in ET.fromstring(body).iter(f"{SITEMAP_NS}loc")]
        base = "https://ballotreels.org"
        self.assertEqual(locs[0], base + "/")
        for path in ("/ca", "/ca/2026/prop-3", "/ca/2026/prop-9",
                     "/ca/2026/cd-1", "/ut", "/ut/2026/amendment-a", "/tx"):
            self.assertIn(base + path, locs)
        self.assertEqual(len(locs), len(set(locs)))
        # Every listed page is a page.
        for loc in locs:
            with self.subTest(loc):
                self.page(loc[len(base):])

    def test_head_requests(self):
        for path in ("/favicon.ico", "/robots.txt", "/sitemap.xml"):
            with self.subTest(path):
                resp, body = self.request(path, method="HEAD")
                self.assertEqual(resp.status, 200)
                self.assertEqual(body, b"")

    def test_other_root_files_still_404(self):
        resp, _ = self.request("/favicon.png")
        self.assertEqual(resp.status, 404)


class HeadTagsTest(ShortUrlTestCase):
    def test_every_page_links_icons_and_manifest(self):
        for path in ("/", "/ut", "/ut/2026/amendment-a"):
            with self.subTest(path):
                tags, raw = self.page(path)
                self.assertEqual(tags.links["manifest"], "/site.webmanifest")
                self.assertEqual(tags.links["apple-touch-icon"],
                                 "/apple-touch-icon.png")
                self.assertIn(b'href="/favicon.svg"', raw)
                self.assertEqual(tags.meta["og:locale"], "en_US")
                self.assertEqual(tags.links["canonical"],
                                 tags.meta["og:url"])


class VideoObjectTest(ShortUrlTestCase):
    def json_ld(self, raw):
        found = re.findall(
            rb'<script type="application/ld\+json">(.*?)</script>', raw)
        return [json.loads(f) for f in found]

    def test_none_without_a_video(self):
        _, raw = self.page("/ut/2026/amendment-a")
        self.assertEqual(self.json_ld(raw), [])

    def test_video_object_once_there_is_a_video(self):
        self.finish_video("ut-2026-11-03-amendment-a",
                          {"video": "/v/abc/1/video.mp4",
                           "poster": "/v/abc/1/poster.jpg"})
        tags, raw = self.page("/ut/2026/amendment-a")
        [doc] = self.json_ld(raw)
        self.assertEqual(doc["@type"], "VideoObject")
        self.assertEqual(doc["name"], tags.title)
        self.assertEqual(doc["description"], tags.meta["description"])
        self.assertEqual(doc["contentUrl"],
                         "https://ballotreels.org/v/abc/1/video.mp4")
        self.assertEqual(doc["thumbnailUrl"],
                         "https://ballotreels.org/v/abc/1/poster.jpg")
        self.assertRegex(doc["uploadDate"],
                         r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")

    def test_script_cannot_be_closed_by_a_title(self):
        meta = pages.PageMeta(title="</script><b>x", description="d",
                              path="/x", image="/p.jpg", video="/v.mp4",
                              video_made=0)
        tag = pages.video_json_ld(meta, "https://ballotreels.org")
        self.assertEqual(tag.count("</script>"), 1)
        self.assertTrue(tag.endswith("</script>"))


class TitlesAgreeTest(ShortUrlTestCase):
    def api(self, path):
        resp, body = self.request(path)
        self.assertEqual(resp.status, 200)
        return json.loads(body)

    def test_api_titles_match_the_rendered_pages(self):
        for page, api in (("/ut", "/api/state/ut"),
                          ("/ut/2026/amendment-a",
                           "/api/contest/ut/2026/amendment-a"),
                          ("/ca/2026/prop-9", "/api/contest/ca/2026/prop-9")):
            with self.subTest(page):
                tags, _ = self.page(page)
                self.assertEqual(self.api(api)["page_title"], tags.title)

    def test_home_title_in_the_app_matches(self):
        app_js = (REPO / "ballotreels" / "site" / "static" /
                  "app.js").read_text(encoding="utf-8")
        self.assertIn(f'document.title = "{pages.HOME_TITLE}";', app_js)


if __name__ == "__main__":
    unittest.main()
