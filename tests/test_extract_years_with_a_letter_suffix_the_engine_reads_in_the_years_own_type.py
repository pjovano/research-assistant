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
SCAN_GREY = 230
SCAN_PIXELS = pymupdf.IRect(0, 0, 60, 80)
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FILE_PAGE = 1
BASELINE = 100.0
LINE_HALF_HEIGHT = 8.0
SUBLEVEL = 1


class ScannedEntryPdf:
    def __init__(self, path: Path, layer_line: str) -> None:
        self._path = path
        self._layer_line = layer_line

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            scan = pymupdf.Pixmap(pymupdf.csGRAY, SCAN_PIXELS, False)
            scan.set_rect(scan.irect, (SCAN_GREY,))
            page.insert_image(page.rect, pixmap=scan, keep_proportion=False)
            page.insert_text((LEFT, BASELINE), self._layer_line, fontsize=FONT_SIZE, fontname=FONT,
                             render_mode=INVISIBLE)
            document.save(self._path)
        return self._path


def engine_block(html: str) -> Block:
    box = (LEFT, BASELINE - LINE_HALF_HEIGHT, RIGHT, BASELINE + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{html}</p>", box, {}, f"/page/{FILE_PAGE}/{TEXT_KIND}/0")


class TestYearsWithALetterSuffixTheEngineReadsInTheYearsOwnType(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _paragraphs(self, layer_line: str, engine_html: str) -> list[str]:
        layer = TextLayer(ScannedEntryPdf(self._directory / "scan.pdf", layer_line).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        result = assembler.assemble(PageBlocks(FILE_PAGE, [engine_block(engine_html)]), [], SUBLEVEL)
        return [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_an_italic_year_whose_suffix_the_layer_reads_as_a_digit_keeps_the_engines_letter(self) -> None:
        paragraphs = self._paragraphs("Tarski, A. 19350 'The concept of truth', in Tarski 1983.",
                                      "Tarski, A. <i>1935a 'The concept of truth'</i>, in Tarski <i>1983</i>.")
        self.assertEqual(["Tarski, A. 1935a 'The concept of truth', in Tarski 1983."], paragraphs)

    def test_a_roman_year_whose_suffix_the_layer_reads_as_a_digit_keeps_the_engines_letter(self) -> None:
        paragraphs = self._paragraphs("— 19356 'Some methodological investigations'.",
                                      "— 1935b 'Some methodological investigations'.")
        self.assertEqual(["— 1935b 'Some methodological investigations'."], paragraphs)


if __name__ == "__main__":
    unittest.main()
