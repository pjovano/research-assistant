from __future__ import annotations

import unittest

import pymupdf

from _support import LiveTree

LiveTree.activate()

import pagetext

from _extract.renders import TEXT_LAYER_JUDGING_DPI, JudgingRenders
from _vaults import LinedPdf, TempVault

POINTS_PER_INCH = 72
PAGES = [["A line of text on the page."]] * 3
TEXT_LAYER_PAGE, PIXEL_PAGE, UNDRAWN_PAGE = 1, 2, 3


class StubLayer:
    def has_text(self, file_page: int) -> bool:
        return True

    def is_drawn(self, file_page: int) -> bool:
        return file_page != UNDRAWN_PAGE


class TestJudgingRenders(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = LinedPdf(self.vault.library / "Doe - 2020 - A Work.pdf", PAGES).write()
        with pymupdf.open(self.pdf) as doc:
            self.page_width_points = doc[0].rect.width

    def dpi_of(self, file_page: int) -> int:
        render = JudgingRenders(self.pdf, StubLayer(), frozenset({PIXEL_PAGE})).by_page([file_page])[file_page]
        return round(pymupdf.Pixmap(render).width * POINTS_PER_INCH / self.page_width_points)

    def test_a_page_read_from_its_text_layer_renders_lighter(self) -> None:
        self.assertEqual(TEXT_LAYER_JUDGING_DPI, self.dpi_of(TEXT_LAYER_PAGE))

    def test_a_page_read_from_pixels_renders_at_full_resolution(self) -> None:
        self.assertEqual(pagetext.DEFAULT_RENDER_DPI, self.dpi_of(PIXEL_PAGE))

    def test_a_page_whose_text_layer_is_not_drawn_renders_at_full_resolution(self) -> None:
        self.assertEqual(pagetext.DEFAULT_RENDER_DPI, self.dpi_of(UNDRAWN_PAGE))


if __name__ == "__main__":
    unittest.main()
