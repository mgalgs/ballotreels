"""film/measure.py illustration_ink: a graphite drawing still lays black
ink, a coloured one keeps its colour, and the surface is valid
premultiplied ARGB."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

from film import measure


def pixels(surf):
    h, w, st = surf.get_height(), surf.get_width(), surf.get_stride()
    return np.frombuffer(bytes(surf.get_data()), np.uint8).reshape(h, st // 4, 4)[:, :w].astype(int)


def ink_of(name, line):
    """illustration_ink of a drawing made here: thick strokes of `line` on
    off-white paper, so the test does not depend on the library's style."""
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / f"{name}.png"
    im = Image.new("RGB", (400, 300), (246, 242, 232))
    d = ImageDraw.Draw(im)
    for y in (80, 150, 220):
        d.line([(60, y), (340, y)], fill=line, width=14)
    im.save(path)
    with mock.patch.object(measure, "load_library", return_value={name: SimpleNamespace(path=path)}):
        measure.illustration_ink.cache_clear()
        surf = measure.illustration_ink(name)[0]
    measure.illustration_ink.cache_clear()
    tmp.cleanup()
    return pixels(surf)


class IllustrationInkTest(unittest.TestCase):
    def test_a_graphite_line_still_reaches_full_black(self):
        px = ink_of("test-graphite", (40, 40, 40))
        solid = px[..., 3] == 255
        self.assertTrue(solid.any())
        # premultiplied colour near 0 at full alpha: near black, as the old graphite ink was
        self.assertLessEqual(int(px[solid][:, :3].max()), 32)

    def test_a_coloured_line_keeps_its_colour(self):
        px = ink_of("test-teal", (40, 130, 130))
        inked = px[..., 3] > 128
        self.assertTrue(inked.any())
        b, g, r = (px[inked][:, i].mean() for i in range(3))  # cairo ARGB32 is BGRA in memory
        self.assertGreater(g, r + 20)

    def test_premultiplied_colour_never_exceeds_alpha(self):
        px = ink_of("test-teal-2", (40, 130, 130))
        self.assertTrue((px[..., :3] <= px[..., 3:4]).all())
