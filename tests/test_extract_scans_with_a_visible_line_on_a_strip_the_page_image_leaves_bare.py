from __future__ import annotations

import unittest

from _scan_fixtures import PagePainting, ScanVault
from _support import LiveTree

LiveTree.activate()

from _extract.console import FORCE_OCR_FLAG

STAMPED_SCAN = (PagePainting.image_above_a_foot_strip, PagePainting.invisible_text,
                PagePainting.visible_line_in_the_foot_strip)


class TestAVisibleLineOnAStripThePageImageLeavesBare(unittest.TestCase):
    def setUp(self) -> None:
        self.scans = ScanVault(self)

    def test_invisible_text_under_a_page_image_is_not_drawn_beside_a_visible_line_below_the_image(self) -> None:
        layer = self.scans.layer(self.scans.filed(STAMPED_SCAN))
        self.assertEqual((True, False), (layer.has_text(1), layer.is_drawn(1)))

    def test_probe_calls_a_work_scanned_whose_only_visible_line_lies_below_its_page_images(self) -> None:
        self.scans.filed(STAMPED_SCAN)
        report = self.scans.probed()
        self.assertEqual((True, [FORCE_OCR_FLAG]), (report["scanned"], report["recommended_flags"]))

    def test_visible_text_is_drawn_when_a_later_image_covers_only_its_first_line(self) -> None:
        layer = self.scans.layer(self.scans.filed((PagePainting.visible_text, PagePainting.image_over_the_first_line)))
        self.assertTrue(layer.is_drawn(1))


if __name__ == "__main__":
    unittest.main()
