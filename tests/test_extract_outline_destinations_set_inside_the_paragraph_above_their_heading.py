from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeLayer, keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.outline import Outline
from _extract.structure import Heading

PAGE_WIDTH = 439.0
PAGE_HEIGHT = 666.0
SECTION_TITLE = "Acknowledgements"
SECTION_LEVEL = 1
CLOSING_PROSE = "The section before closes with this paragraph, whose last line the destination names."
RUN_IN_PROSE = "Acknowledgements The author thanks a colleague for her comments."
CLOSING_TOP, CLOSING_BOTTOM = 250.0, 320.0
RUN_IN_TOP, RUN_IN_BOTTOM = 333.0, 370.0
DESTINATION_IN_THE_CLOSING_LAST_LINE = 310.0
DESTINATION_AT_THE_RUN_IN_TOP = 333.0


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_destination_at_depth(self, depth: float) -> Path:
        with pymupdf.open() as document:
            document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": 1, "to": pymupdf.Point(0, depth)}
            document.set_toc([[SECTION_LEVEL, SECTION_TITLE, 1, destination]])
            document.save(self._path)
        return self._path


def text_block(text: str, top: float, bottom: float) -> Block:
    return Block(1, "Text", f"<p>{text}</p>", (40.0, top, 400.0, bottom), {}, f"/page/1/Text/{top}")


class TestOutlineDestinationsSetInsideTheParagraphAboveTheirHeading(unittest.TestCase):
    def _texts(self, destination_depth: float) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            due = Outline(OutlinedPdf(directory).with_destination_at_depth(destination_depth)).headings()
        blocks = [text_block(CLOSING_PROSE, CLOSING_TOP, CLOSING_BOTTOM),
                  text_block(RUN_IN_PROSE, RUN_IN_TOP, RUN_IN_BOTTOM)]
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), due, SECTION_LEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_destination_inside_the_last_line_of_the_paragraph_above_opens_the_heading_after_that_paragraph(
            self) -> None:
        self.assertEqual([CLOSING_PROSE, SECTION_TITLE, RUN_IN_PROSE],
                         self._texts(DESTINATION_IN_THE_CLOSING_LAST_LINE))

    def test_a_destination_at_the_top_of_the_paragraph_printing_the_title_opens_the_heading_above_it(
            self) -> None:
        self.assertEqual([CLOSING_PROSE, SECTION_TITLE, RUN_IN_PROSE], self._texts(DESTINATION_AT_THE_RUN_IN_TOP))


if __name__ == "__main__":
    unittest.main()
