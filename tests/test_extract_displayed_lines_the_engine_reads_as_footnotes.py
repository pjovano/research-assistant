from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY = "Then the theory entails the following statement:"
DISPLAYED_LINE = "(3) To be in a state is to be in state F."
BODY_BASELINE = 100.0
DISPLAYED_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0


class DisplayedLinePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text in [(BODY_BASELINE, BODY), (DISPLAYED_BASELINE, DISPLAYED_LINE)]:
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(kind: str, text: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, f"<p>{text}</p>", box, {}, f"/page/1/{kind}/{baseline}")


class TestDisplayedLinesTheEngineReadsAsFootnotes(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(DisplayedLinePdf(Path(directory.name) / "displayed.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        blocks = [engine_block(TEXT_KIND, BODY, BODY_BASELINE),
                  engine_block(FOOTNOTE_KIND, DISPLAYED_LINE, DISPLAYED_BASELINE)]
        self.result = assembler.assemble(PageBlocks(1, blocks), [], 1)

    def test_a_displayed_line_opening_with_a_parenthesised_number_under_no_mark_defines_no_footnote(self) -> None:
        self.assertEqual([], self.result.definitions)

    def test_a_displayed_line_opening_with_a_parenthesised_number_under_no_mark_stays_body_text(self) -> None:
        paragraphs = [element.text for element in self.result.elements if isinstance(element, Paragraph)]
        self.assertEqual([BODY, DISPLAYED_LINE], paragraphs)


if __name__ == "__main__":
    unittest.main()
