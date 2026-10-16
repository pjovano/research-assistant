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

PAGE_WIDTH = 395.0
PAGE_HEIGHT = 539.0
DEPTH_ABOVE_THE_FIRST_PARAGRAPH = 36.0
DEPTH_BELOW_THE_PAGE_HEAD = 172.0
SECTION_TITLE = "Introduction"
SECTION_LEVEL = 1
DESTINATION_NAME = "section.1"
FIRST_PROSE = "The introduction opens on this page with no heading printed above it."
SECOND_PROSE = "And it carries on in a second paragraph down to the foot of the page."


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_explicit_destination_at_depth(self, depth: float) -> Path:
        with self._outlined(depth) as document:
            document.save(self._path)
        return self._path

    def with_named_destination_at_depth(self, depth: float) -> Path:
        with self._outlined(depth) as document:
            item = document.get_toc(simple=False)[0][3]["xref"]
            page = document.page_xref(0)
            destination = document.get_new_xref()
            document.update_object(destination, f"<< /D [{page} 0 R /XYZ 0 {PAGE_HEIGHT - depth} null] >>")
            document.xref_set_key(item, "A", f"<< /S /GoTo /D ({DESTINATION_NAME}) >>")
            names = f"<< /Dests << /Names [({DESTINATION_NAME}) {destination} 0 R] >> >>"
            document.xref_set_key(document.pdf_catalog(), "Names", names)
            document.save(self._path)
        return self._path

    @staticmethod
    def _outlined(depth: float) -> pymupdf.Document:
        document = pymupdf.open()
        document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        document.set_toc([[SECTION_LEVEL, SECTION_TITLE, 1, {"kind": pymupdf.LINK_GOTO, "to": pymupdf.Point(0, depth)}]])
        return document


def text_block(text: str, top: float, bottom: float) -> Block:
    return Block(1, "Text", f"<p>{text}</p>", (40.0, top, 360.0, bottom), {}, f"/page/1/Text/{top}")


class TestOutlineDestinationsSetExplicitlyOrByName(unittest.TestCase):
    def _position(self, write) -> float:
        with tempfile.TemporaryDirectory() as directory:
            return Outline(write(OutlinedPdf(directory))).headings()[0].position

    def test_an_explicit_destination_names_its_depth_below_the_page_top(self) -> None:
        position = self._position(
            lambda pdf: pdf.with_explicit_destination_at_depth(DEPTH_BELOW_THE_PAGE_HEAD))
        self.assertAlmostEqual(DEPTH_BELOW_THE_PAGE_HEAD, position)

    def test_a_named_destination_names_its_depth_below_the_page_top(self) -> None:
        position = self._position(lambda pdf: pdf.with_named_destination_at_depth(DEPTH_BELOW_THE_PAGE_HEAD))
        self.assertAlmostEqual(DEPTH_BELOW_THE_PAGE_HEAD, position)

    def test_an_explicit_destination_above_the_first_paragraph_opens_its_heading_above_that_paragraph(
            self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = OutlinedPdf(directory).with_explicit_destination_at_depth(DEPTH_ABOVE_THE_FIRST_PARAGRAPH)
            due = Outline(pdf).headings()
        blocks = [text_block(FIRST_PROSE, 79.0, 254.0), text_block(SECOND_PROSE, 254.0, 464.0)]
        elements = page_assembler(FakeLayer(), keep_everything()).assemble(PageBlocks(1, blocks), due, 2).elements
        texts = [element.title if isinstance(element, Heading) else element.text for element in elements[1:]]
        self.assertEqual([SECTION_TITLE, FIRST_PROSE, SECOND_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
