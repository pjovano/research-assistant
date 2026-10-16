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
PAGE_HEIGHT = 666.142
SHARED_DEPTH = 36.0
OTHER_DEPTH = 300.0
DESTINATION_LEFT = 72.0
TITLES = ["I.", "II.", "III."]
CARRIED_PROSE = "the argument of the section before carries on here."
SECTION_PROSE = "II. The second section opens partway down the page."
PROSE_PAST_THE_TITLE = "The second section opens partway down the page."


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_depths(self, depths: list[float]) -> Path:
        with pymupdf.open() as document:
            for _depth in depths:
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            document.set_toc([[1, title, page,
                               {"kind": pymupdf.LINK_GOTO, "to": pymupdf.Point(DESTINATION_LEFT, depth)}]
                              for page, (title, depth) in enumerate(zip(TITLES, depths), start=1)])
            document.save(self._path)
        return self._path


def text_block(text: str, top: float, bottom: float) -> Block:
    return Block(2, "Text", f"<p>{text}</p>", (0.0, top, 100.0, bottom), {}, f"/page/2/Text/{top}")


class TestAnOutlineNamingOneDepthForEveryEntry(unittest.TestCase):
    def _headings(self, depths: list[float]) -> list:
        with tempfile.TemporaryDirectory() as directory:
            return Outline(OutlinedPdf(directory).with_depths(depths)).headings()

    def test_every_entry_of_an_outline_naming_one_depth_for_all_is_the_page_top(self) -> None:
        positions = [heading.position for heading in self._headings([SHARED_DEPTH] * len(TITLES))]
        self.assertEqual([PAGE_TOP] * len(TITLES), positions)

    def test_an_outline_whose_entries_name_different_depths_keeps_each_depth(self) -> None:
        positions = [heading.position for heading in self._headings([SHARED_DEPTH, SHARED_DEPTH, OTHER_DEPTH])]
        self.assertTrue(all(position != PAGE_TOP for position in positions))

    def test_an_entry_of_such_an_outline_opens_at_the_paragraph_printing_its_title_partway_down_once(self) -> None:
        due = [heading for heading in self._headings([SHARED_DEPTH] * len(TITLES)) if heading.file_page == 2]
        blocks = [text_block(CARRIED_PROSE, 40.0, 200.0), text_block(SECTION_PROSE, 300.0, 400.0)]
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(2, blocks), due, 2).elements[1:]
        texts = [element.title if isinstance(element, Heading) else element.text for element in elements]
        self.assertEqual([CARRIED_PROSE, "II.", PROSE_PAST_THE_TITLE], texts)


if __name__ == "__main__":
    unittest.main()
