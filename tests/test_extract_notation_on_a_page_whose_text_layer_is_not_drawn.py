from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "tiro"
FONT_SIZE = 10.0
INVISIBLE = 3
VISIBLE = 0
SCAN_GREY = 230
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FILE_PAGE = 1
BASELINE = 100.0
LINE_HALF_HEIGHT = 8.0
LAYER_LINE = "a die shows 14 of its faces"
ENGINE_HTML = "a die shows <math>\\frac{1}{6}</math> of its faces"
ENGINE_READING = "a die shows $\\frac{1}{6}$ of its faces"
LAYER_READING = "a die shows $\\frac{1}{4}$ of its faces"


class SentencePdf:
    def __init__(self, path: Path, render_mode: int) -> None:
        self._path = path
        self._render_mode = render_mode

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            if self._render_mode == INVISIBLE:
                self._scan(page)
            page.insert_text((LEFT, BASELINE), LAYER_LINE, fontsize=FONT_SIZE, fontname=FONT,
                             render_mode=self._render_mode)
            document.save(self._path)
        return self._path

    @staticmethod
    def _scan(page: pymupdf.Page) -> None:
        scan = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
        scan.set_rect(scan.irect, (SCAN_GREY,))
        page.insert_image(page.rect, pixmap=scan, keep_proportion=False)


def engine_block() -> Block:
    box = (LEFT, BASELINE - LINE_HALF_HEIGHT, RIGHT, BASELINE + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{ENGINE_HTML}</p>", box, {}, f"/page/{FILE_PAGE}/{TEXT_KIND}/0")


class TestNotationOnAPageWhoseTextLayerIsNotDrawn(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _paragraphs(self, render_mode: int) -> list[str]:
        layer = TextLayer(SentencePdf(self._directory / "page.pdf", render_mode).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        result = assembler.assemble(PageBlocks(FILE_PAGE, [engine_block()]), [], 1)
        return [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_a_formula_keeps_the_engines_reading_over_a_text_layer_lying_invisibly_under_the_page_image(self) -> None:
        self.assertEqual([ENGINE_READING], self._paragraphs(INVISIBLE))

    def test_a_formula_still_takes_the_correction_a_drawn_text_layer_names(self) -> None:
        self.assertEqual([LAYER_READING], self._paragraphs(VISIBLE))


if __name__ == "__main__":
    unittest.main()
