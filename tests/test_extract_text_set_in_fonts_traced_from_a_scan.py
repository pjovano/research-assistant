from __future__ import annotations

import unittest

from _scan_fixtures import PagePainting, ScanVault
from _support import LiveTree

LiveTree.activate()

from _extract.console import FORCE_OCR_FLAG

TRACED_PAGE = (PagePainting.image, PagePainting.visible_text_in_a_font_traced_from_a_scan)
DRAWN_PAGE_WITH_A_TRACED_LINE = (PagePainting.visible_text,
                                 PagePainting.visible_line_in_the_foot_strip_in_a_font_traced_from_a_scan)


class TestTextSetInFontsTracedFromAScan(unittest.TestCase):
    def setUp(self) -> None:
        self.scans = ScanVault(self)

    def test_visible_text_set_in_a_font_traced_from_a_scan_is_not_drawn(self) -> None:
        layer = self.scans.layer(self.scans.filed(TRACED_PAGE))
        self.assertEqual((True, False), (layer.has_text(1), layer.is_drawn(1)))

    def test_probe_calls_a_work_whose_text_is_set_in_fonts_traced_from_a_scan_scanned(self) -> None:
        self.scans.filed(TRACED_PAGE)
        report = self.scans.probed()
        self.assertEqual((True, [FORCE_OCR_FLAG]), (report["scanned"], report["recommended_flags"]))

    def test_a_page_setting_one_line_in_a_font_traced_from_a_scan_is_drawn(self) -> None:
        layer = self.scans.layer(self.scans.filed(DRAWN_PAGE_WITH_A_TRACED_LINE))
        self.assertTrue(layer.is_drawn(1))


if __name__ == "__main__":
    unittest.main()
