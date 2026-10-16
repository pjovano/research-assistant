from __future__ import annotations

import unittest

from _scan_fixtures import PagePainting, ScanVault
from _support import LiveTree

LiveTree.activate()

from _extract.console import FORCE_OCR_FLAG
from _vaults import TextPdf


class TestTextLaidUnderPageImages(unittest.TestCase):
    def setUp(self) -> None:
        self.scans = ScanVault(self)
        self.pdf = self.scans.filed((PagePainting.image, PagePainting.invisible_text))

    def test_a_text_layer_laid_invisibly_under_the_page_images_is_not_drawn(self) -> None:
        layer = self.scans.layer(self.pdf)
        self.assertEqual((True, False), (layer.has_text(1), layer.is_drawn(1)))

    def test_a_text_layer_the_page_draws_is_drawn(self) -> None:
        self.assertTrue(self.scans.layer(TextPdf(self.scans.vault.library / "Doe - 2020 - A Drawn Work.pdf").write())
                        .is_drawn(1))

    def test_probe_calls_a_work_whose_text_lies_invisibly_under_its_page_images_scanned(self) -> None:
        report = self.scans.probed()
        self.assertEqual((True, [FORCE_OCR_FLAG]), (report["scanned"], report["recommended_flags"]))


class TestVisibleTextPaintedBeneathAPageImage(unittest.TestCase):
    def setUp(self) -> None:
        self.scans = ScanVault(self)

    def test_visible_text_a_later_page_image_covers_is_not_drawn(self) -> None:
        layer = self.scans.layer(self.scans.filed((PagePainting.visible_text, PagePainting.image)))
        self.assertEqual((True, False), (layer.has_text(1), layer.is_drawn(1)))

    def test_probe_calls_a_work_whose_visible_text_lies_beneath_its_page_images_scanned(self) -> None:
        self.scans.filed((PagePainting.visible_text, PagePainting.image))
        report = self.scans.probed()
        self.assertEqual((True, [FORCE_OCR_FLAG]), (report["scanned"], report["recommended_flags"]))

    def test_visible_text_painted_over_a_background_image_is_drawn(self) -> None:
        layer = self.scans.layer(self.scans.filed((PagePainting.image, PagePainting.visible_text)))
        self.assertTrue(layer.is_drawn(1))


if __name__ == "__main__":
    unittest.main()
