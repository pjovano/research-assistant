from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeLayer, keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.outline import PAGE_TOP, Outline
from _extract.structure import Heading

PAGE_WIDTH = 439.37
PAGE_HEIGHT_WITH_A_FRACTION = 666.142
PAGE_HEIGHT = 649.0
WITHIN_A_POINT_OF_THE_TOP = 0.5
PAST_A_POINT_BELOW_THE_TOP = 2.0
SECTION_TITLE = "2."
OPENING_PROSE = "The section before carries on here."
SECTION_PROSE = "2. The numbered section opens mid-page."
PROSE_PAST_THE_TITLE = "The numbered section opens mid-page."


class OutlinedPdf:
    def __init__(self, directory: str, page_height: float) -> None:
        self._path = Path(directory) / "outlined.pdf"
        self._page_height = page_height

    def with_destination_at(self, destination_y: float) -> Path:
        with pymupdf.open() as document:
            document.new_page(width=PAGE_WIDTH, height=self._page_height)
            destination = {"kind": 1, "to": pymupdf.Point(0, self._page_height - destination_y)}
            document.set_toc([[1, SECTION_TITLE, 1, destination]])
            document.save(self._path)
        return self._path


def text_block(text: str, top: float, bottom: float) -> Block:
    return Block(1, "Text", f"<p>{text}</p>", (0.0, top, 100.0, bottom), {}, f"/page/1/Text/{top}")


class TestDestinationsAtThePageEdge(unittest.TestCase):
    def _position(self, page_height: float, destination_y: float) -> float:
        with tempfile.TemporaryDirectory() as directory:
            path = OutlinedPdf(directory, page_height).with_destination_at(destination_y)
            return Outline(path).headings()[0].position

    def test_a_destination_the_page_height_rounds_past_by_a_fraction_is_the_page_top(self) -> None:
        self.assertEqual(PAGE_TOP, self._position(PAGE_HEIGHT_WITH_A_FRACTION, PAGE_HEIGHT_WITH_A_FRACTION))

    def test_a_destination_within_a_point_of_the_page_top_is_the_page_top(self) -> None:
        self.assertEqual(PAGE_TOP, self._position(PAGE_HEIGHT, PAGE_HEIGHT - WITHIN_A_POINT_OF_THE_TOP))

    def test_a_destination_past_a_point_below_the_page_top_keeps_its_depth(self) -> None:
        position = self._position(PAGE_HEIGHT, PAGE_HEIGHT - PAST_A_POINT_BELOW_THE_TOP)
        self.assertAlmostEqual(PAST_A_POINT_BELOW_THE_TOP, position)

    def test_a_heading_whose_destination_the_page_height_rounds_past_opens_at_the_paragraph_printing_it_once(
            self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = OutlinedPdf(directory, PAGE_HEIGHT_WITH_A_FRACTION)
            due = Outline(pdf.with_destination_at(PAGE_HEIGHT_WITH_A_FRACTION)).headings()
        blocks = [text_block(OPENING_PROSE, 40.0, 120.0), text_block(SECTION_PROSE, 130.0, 300.0)]
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), due, 2).elements[1:]
        texts = [element.title if isinstance(element, Heading) else element.text for element in elements]
        self.assertEqual([OPENING_PROSE, SECTION_TITLE, PROSE_PAST_THE_TITLE], texts)


if __name__ == "__main__":
    unittest.main()
