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
from _extract.writer import NoteWriter

FILE_PAGE = 1
FONT = "cour"
FONT_SIZE = 9.0
LINE_PITCH = 12.0
FIRST_BASELINE = 100.0
CHAR_WIDTH = pymupdf.get_text_length("x", FONT, FONT_SIZE)
MARGIN = 40.0
OPENING_INDENT_CHARS = 3
MEASURE_CHARS = 60
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
SUBLEVEL = 2
FLUSH, INDENTED = 0, OPENING_INDENT_CHARS
OPENING_PARAGRAPH = [(INDENTED, "The oppositions this book treats are listed with pages on"),
                     (FLUSH, "which each of them is discussed in the chapters above in the")]
CLOSING_LINE = (FLUSH, "order of the alphabet and without comment")
SHORT_ENTRIES = [(FLUSH, "Absolute/Relative, 50, 81f, 83, 103, 120"), (FLUSH, "Being/Nothingness, 125f"),
                 (FLUSH, "Bounded/Unbounded, 81, 167")]
RESUMED_LINE = (FLUSH, "order of the alphabet, so that a reader can find them")


def justified(text: str, width_chars: int) -> str:
    words = text.split()
    spaces = width_chars - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


class FlushBlocksPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, blocks: list[list[tuple[int, str]]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            lines = [line for block in blocks for line in block]
            for row, (indent, text) in enumerate(lines):
                fills = row < len(OPENING_PARAGRAPH)
                printed = justified(text, MEASURE_CHARS - indent) if fills else text
                page.insert_text((MARGIN + indent * CHAR_WIDTH, FIRST_BASELINE + row * LINE_PITCH), printed,
                                 fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_blocks(blocks: list[list[tuple[int, str]]]) -> list[Block]:
    engine, row = [], 0
    for index, lines in enumerate(blocks):
        top = FIRST_BASELINE + (row - 1) * LINE_PITCH + 2.0
        bottom = FIRST_BASELINE + (row + len(lines) - 1) * LINE_PITCH + 3.0
        html = "<p>" + " ".join(text for _indent, text in lines) + "</p>"
        engine.append(Block(FILE_PAGE, "Text", html, (MARGIN - 1.0, top, PAGE_WIDTH - MARGIN, bottom), {},
                            f"/page/{FILE_PAGE}/Text/{index}"))
        row += len(lines)
    return engine


class TestFlushBlocksBelowABlockWhoseLastLineStopsShortOfTheMeasure(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "blocks.pdf"

    def paragraphs(self, blocks: list[list[tuple[int, str]]]) -> list[str]:
        layer = TextLayer(FlushBlocksPdf(self._path).write(blocks))
        self.addCleanup(layer.close)
        elements = page_assembler(layer, keep_everything()).assemble(
            PageBlocks(FILE_PAGE, engine_blocks(blocks)), [], SUBLEVEL).elements
        return NoteWriter().render(elements[1:], []).text.strip().split("\n\n")

    def test_a_flush_block_below_a_block_whose_last_line_stops_short_of_the_measure_opens_a_paragraph(
            self) -> None:
        blocks = [OPENING_PARAGRAPH + [CLOSING_LINE], *([entry] for entry in SHORT_ENTRIES)]
        expected = [" ".join(text for _indent, text in blocks[0])] + [text for _indent, text in SHORT_ENTRIES]
        self.assertEqual(expected, [" ".join(paragraph.split()) for paragraph in self.paragraphs(blocks)])

    def test_a_flush_block_below_a_block_whose_last_line_fills_the_measure_resumes_its_paragraph(self) -> None:
        blocks = [OPENING_PARAGRAPH, [RESUMED_LINE]]
        expected = [" ".join(text for _indent, text in OPENING_PARAGRAPH + [RESUMED_LINE])]
        self.assertEqual(expected, [" ".join(paragraph.split()) for paragraph in self.paragraphs(blocks)])


if __name__ == "__main__":
    unittest.main()
