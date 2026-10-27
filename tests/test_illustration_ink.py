"""film/measure.py illustration_ink: a graphite library file still lays
black ink, and the surface is valid premultiplied ARGB."""

import unittest

import numpy as np

from film import measure


def pixels(surf):
    h, w, st = surf.get_height(), surf.get_width(), surf.get_stride()
    return np.frombuffer(bytes(surf.get_data()), np.uint8).reshape(h, st // 4, 4)[:, :w].astype(int)


class IllustrationInkTest(unittest.TestCase):
    def test_a_graphite_line_still_reaches_full_black(self):
        px = pixels(measure.illustration_ink('trade-off')[0])
        solid = px[..., 3] == 255
        self.assertTrue(solid.any())
        # premultiplied colour near 0 at full alpha: near black, as the old graphite ink was
        self.assertLessEqual(int(px[solid][:, :3].max()), 32)

    def test_premultiplied_colour_never_exceeds_alpha(self):
        px = pixels(measure.illustration_ink('trade-off')[0])
        self.assertTrue((px[..., :3] <= px[..., 3:4]).all())
