"""film/measure.py's link: the measure's own page on the site, under the
caption on every frame, from the opening card to the sources card, clear
of everything else the film draws, and on the site's configured address."""

import os
import unittest
from unittest import mock

import videobuilder as vb

from ballotreels.site import pages
from tests.helpers import film_measure

m = film_measure()


def overlap(a, b):
    """True if boxes a and b share more than a pixel's sliver."""
    w = min(a.right, b.right) - max(a.x, b.x)
    h = min(a.bottom, b.bottom) - max(a.y, b.y)
    return w > 1 and h > 1


def sample_frames():
    """The opening card, one frame inside every section (the charts and
    their source lines, the sides slide), and the sources card."""
    frames = [0, 1]
    for s in m.BOARD.sections:
        frames.append((s.start + s.end) // 2)
        frames += [(c.start + c.end) // 2 for c in s.charts]
    frames += [m.BOARD.narration_end + 20, m.BOARD.end - 1]
    return sorted(set(frames))


class LinkTextTest(unittest.TestCase):
    def test_the_link_is_the_measure_s_short_path_without_a_scheme(self):
        self.assertEqual(m.LINK, "ballotreels.org/ca/2026/prop-2")

    def test_the_path_is_the_site_s_own(self):
        self.assertEqual(pages.contest_path("ut", "ut-2026-11-03",
                                            "ut-2026-11-03-amendment-A"),
                         "/ut/2026/amendment-a")
        self.assertEqual(pages.display_url("https://ballotreels.org/",
                                           "/ut/2026/amendment-a"),
                         "ballotreels.org/ut/2026/amendment-a")
        self.assertEqual(pages.display_url("http://localhost:8080", "/ca"),
                         "localhost:8080/ca")

    def test_the_domain_follows_the_site_url_setting(self):
        with mock.patch.dict(os.environ, {
                "BALLOTREELS_SITE_URL": "https://staging.example.org/",
                "BALLOTREELS_CONTEST": str(m.CONTEST_DIR)}):
            mod = vb.load_module(m.__file__)
        self.assertEqual(mod.LINK, "staging.example.org/ca/2026/prop-2")


class LinkLayoutTest(unittest.TestCase):
    def test_it_sits_between_the_caption_and_the_footer_inside_the_frame(self):
        for fmt, L in m.LAYOUTS.items():
            for view in ("", "page_"):
                link, scrap = L[view + "link"], L[view + "scrap"]
                footer = L[view + "footer"]
                self.assertGreaterEqual(link.y, scrap.bottom, (fmt, view))
                self.assertLessEqual(link.bottom, L["H"], (fmt, view))
                self.assertLessEqual(footer.bottom, L["H"], (fmt, view))
                self.assertFalse(overlap(link, footer), (fmt, view))

    def test_it_takes_one_line_at_its_full_size(self):
        for fmt, L in m.LAYOUTS.items():
            self.assertLessEqual(m.text.measure(m.LINK, L["link_font"]), L["link"].w, fmt)
            self.assertLessEqual(m.text.line_height(L["link_font"]), L["link"].h + 1, fmt)

    def test_it_is_legible_on_a_phone(self):
        # at least 12 css px on a 390 px wide phone screen
        L = m.LAYOUTS["9x16"]
        self.assertGreaterEqual(L["link_font"].size * 390 / L["W"], 12)

    def test_the_caption_still_fits_its_scrap(self):
        for fmt, L in m.LAYOUTS.items():
            lines = L["caption_lines"] * m.text.line_height(L["caption_font"])
            self.assertLess(lines, L["scrap"].h - 10, fmt)


class LinkOnEveryFrameTest(unittest.TestCase):
    def test_every_frame_shows_the_link_clear_of_every_other_mark(self):
        for fmt in m.LAYOUTS:
            for n in sample_frames():
                marks = m.FILM.frame(n, fmt).marks
                links = [b for name, b in marks if name == "link"]
                self.assertEqual(len(links), 1, (fmt, n))
                for name, box in marks:
                    if name != "link":
                        self.assertFalse(overlap(links[0], box), (fmt, n, name))


if __name__ == "__main__":
    unittest.main()
