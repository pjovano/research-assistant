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
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FILE_PAGE = 1
FIRST_BASELINE = 100.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 8.0


class ScannedPagePdf:
    def __init__(self, path: Path, layer_lines: list[str]) -> None:
        self._path = path
        self._layer_lines = layer_lines

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._scan(page)
            for row, text in enumerate(self._layer_lines):
                page.insert_text((LEFT, baseline(row)), text, fontsize=FONT_SIZE, fontname=FONT, render_mode=INVISIBLE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _scan(page: pymupdf.Page) -> None:
        scan = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
        scan.set_rect(scan.irect, (SCAN_GREY,))
        page.insert_image(page.rect, pixmap=scan, keep_proportion=False)


def baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def engine_block(row: int, html: str) -> Block:
    box = (LEFT, baseline(row) - LINE_HALF_HEIGHT, RIGHT, baseline(row) + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{html}</p>", box, {}, f"/page/{FILE_PAGE}/{TEXT_KIND}/{row}")


class TestNumeralsTheEngineReadsFromPixelsAsDigitsMixedWithItalicLetters(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _paragraphs(self, layer_line: str, engine_html: str) -> list[str]:
        layer = TextLayer(ScannedPagePdf(self._directory / "scan.pdf", [layer_line]).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        result = assembler.assemble(PageBlocks(FILE_PAGE, [engine_block(0, engine_html)]), [], 1)
        return [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_a_citation_read_with_italic_letters_among_its_digits_takes_the_layers_digits_behind_its_prefix(self) -> None:
        paragraphs = self._paragraphs("beyond that limit (B585), we are enabled",
                                      "beyond that limit (B<i>j</i>85<i>j</i>), we are enabled")
        self.assertEqual(["beyond that limit (B585), we are enabled"], paragraphs)

    def test_a_numeral_whose_last_digit_is_read_as_an_italic_letter_takes_the_layers_digits(self) -> None:
        paragraphs = self._paragraphs("prevails upon the opponent (B805).", "prevails upon the opponent (B80<i>j</i>).")
        self.assertEqual(["prevails upon the opponent (B805)."], paragraphs)

    def test_a_numeral_set_apart_from_its_prefix_takes_the_layers_digits(self) -> None:
        paragraphs = self._paragraphs("through experience (B 831).", "through experience (B <i>j</i>31<i>i</i>).")
        self.assertEqual(["through experience (B 831)."], paragraphs)

    def test_a_misspelled_word_keeps_the_engines_reading_beside_a_corrected_numeral(self) -> None:
        paragraphs = self._paragraphs("Kant argues (B562) that", "Kamt argues (B<i>j</i>62<i>j</i>) that")
        self.assertEqual(["Kamt argues (B562) that"], paragraphs)

    def test_a_numeral_the_layer_prints_with_letters_keeps_the_engines_reading(self) -> None:
        paragraphs = self._paragraphs("as noted (B445n) there", "as noted (B44<i>j</i>n) there")
        self.assertEqual(["as noted (B44jn) there"], paragraphs)

    def test_a_capital_letter_the_layer_reads_as_a_digit_keeps_the_engines_reading(self) -> None:
        paragraphs = self._paragraphs("practical employment. (8836)", "practical employment. (B836)")
        self.assertEqual(["practical employment. (B836)"], paragraphs)

    def test_a_numeral_whose_digits_the_layer_drops_keeps_the_engines_reading(self) -> None:
        paragraphs = self._paragraphs("Allison 201. Kant", "Allison 2014a. Kant")
        self.assertEqual(["Allison 2014a. Kant"], paragraphs)


if __name__ == "__main__":
    unittest.main()
