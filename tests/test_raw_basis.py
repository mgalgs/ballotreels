"""A basis matched against a PDF's printed-order text (pdftotext -raw),
where a scan's doubled text layer defeats the default reading order
(checks._loose_archived)."""

import shutil
import unittest
from pathlib import Path

from ballotreels.checks import _archived_text, _loose, _loose_archived

ROOT = Path(__file__).resolve().parent.parent
TULELAKE = (ROOT / "data/ca-2026-11-03/tulelake-fpd-measure-i/sources/"
            "argument-in-favor.pdf")


@unittest.skipUnless(shutil.which("pdftotext"), "needs pdftotext")
class RawBasisTest(unittest.TestCase):
    def test_basis_found_in_printed_order(self):
        basis = _loose("Without increased funding the result could be a "
                       "reduction in fire and medical services")
        self.assertNotIn(basis, _loose(_archived_text(TULELAKE)))
        self.assertIn(basis, _loose_archived(TULELAKE))

    def test_words_still_in_order(self):
        self.assertNotIn(_loose("Without funding increased the result"),
                         _loose_archived(TULELAKE))
