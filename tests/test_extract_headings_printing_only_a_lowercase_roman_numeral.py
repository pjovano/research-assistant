from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
LINE_PITCH = 12.0
MARGIN = 50.0
PAGE_WIDTH, PAGE_HEIGHT = 400.0, 600.0
PAGE_MIDDLE = PAGE_WIDTH / 2
HEADING_SUBLEVEL = 6
PARAGRAPH_ABOVE = "People judge decisions by events and blame the prudent for bad luck."
PARAGRAPH_BELOW = "It is a weakness and an injustice to judge decisions by their events."


class NumeralDividedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, numeral: str) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text, left in self._lines(numeral):
                page.insert_text((left, baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _lines(numeral: str) -> list[tuple[float, str, float]]:
        numeral_left = PAGE_MIDDLE - pymupdf.get_text_length(numeral, FONT, FONT_SIZE) / 2
        return [(100.0, PARAGRAPH_ABOVE, MARGIN), (100.0 + 2 * LINE_PITCH, numeral, numeral_left),
                (100.0 + 4 * LINE_PITCH, PARAGRAPH_BELOW, MARGIN)]


def engine_blocks(layer: TextLayer, numeral: str) -> list[Block]:
    lines = layer.lines(FILE_PAGE)
    kinds = ["Text", "SectionHeader", "Text"]
    htmls = [f"<p>{PARAGRAPH_ABOVE}</p>", f"<p>{numeral}</p>", f"<p>{PARAGRAPH_BELOW}</p>"]
    return [Block(FILE_PAGE, kind, html, (line.x0, line.y0, line.x1, 2 * line.center[1] - line.y0), {},
                  f"/page/{FILE_PAGE}/{kind}/{index}")
            for index, (kind, html, line) in enumerate(zip(kinds, htmls, lines))]


class TestHeadingsPrintingOnlyALowercaseRomanNumeral(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "numeral.pdf"

    def headings(self, numeral: str) -> list[str]:
        layer = TextLayer(NumeralDividedPdf(self._path).write(numeral))
        self.addCleanup(layer.close)
        page = PageBlocks(FILE_PAGE, engine_blocks(layer, numeral))
        elements = page_assembler(layer, keep_everything()).assemble(page, [], HEADING_SUBLEVEL).elements
        return [element.title for element in elements if isinstance(element, Heading)]

    def test_a_heading_printing_only_a_lowercase_roman_numeral_opens_a_section(self) -> None:
        self.assertEqual(["v"], self.headings("v"))

    def test_a_heading_printing_only_an_uppercase_roman_numeral_opens_a_section(self) -> None:
        self.assertEqual(["V"], self.headings("V"))

    def test_a_heading_printing_a_lowercase_word_spelt_in_roman_letters_reads_as_a_fragment(self) -> None:
        self.assertEqual([], self.headings("mild"))


if __name__ == "__main__":
    unittest.main()
