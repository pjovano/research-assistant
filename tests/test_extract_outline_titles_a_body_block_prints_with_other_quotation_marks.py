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

PAGE_WIDTH = 440.0
PAGE_HEIGHT = 660.0
SECTION_LEVEL = 1
SECTION_TITLE = "II. The reach of the critic's method: the shape of the argument"
SMALL_CAPITALS_READING = "ii. the reach of the critic’s method: the shape of the argument"
CARRIED_PROSE = "of the first part, and it is to a brief review of the second that we now turn."
OPENING_PROSE = "The argument proposes a general pattern for the errors it finds."
RUN_IN_PROSE = f"{SMALL_CAPITALS_READING} {OPENING_PROSE}"


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_entry_at_the_page_top(self) -> Path:
        with pymupdf.open() as document:
            document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": pymupdf.LINK_GOTO, "to": pymupdf.Point(0, 0)}
            document.set_toc([[SECTION_LEVEL, SECTION_TITLE, 1, destination]])
            document.save(self._path)
        return self._path


def text_block(text: str, top: float, bottom: float) -> Block:
    return Block(1, "Text", f"<p>{text}</p>", (40.0, top, 400.0, bottom), {}, f"/page/1/Text/{top}")


class TestOutlineTitlesABodyBlockPrintsWithOtherQuotationMarks(unittest.TestCase):
    def _texts(self, blocks: list[Block]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            due = Outline(OutlinedPdf(directory).with_entry_at_the_page_top()).headings()
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), due, SECTION_LEVEL + 1).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_block_printing_only_the_title_opens_the_heading_where_it_prints_in_place_of_the_block(self) -> None:
        blocks = [text_block(CARRIED_PROSE, 58.0, 85.0), text_block(SMALL_CAPITALS_READING, 104.0, 141.0),
                  text_block(OPENING_PROSE, 150.0, 306.0)]
        self.assertEqual([CARRIED_PROSE, SECTION_TITLE, OPENING_PROSE], self._texts(blocks))

    def test_a_paragraph_opening_with_the_title_opens_the_heading_there_and_keeps_the_prose_past_it(self) -> None:
        blocks = [text_block(CARRIED_PROSE, 58.0, 85.0), text_block(RUN_IN_PROSE, 104.0, 306.0)]
        self.assertEqual([CARRIED_PROSE, SECTION_TITLE, OPENING_PROSE], self._texts(blocks))


if __name__ == "__main__":
    unittest.main()
