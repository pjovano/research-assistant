from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.layer import TextLayer
from _extract.layerlines import PageLines
from _extract.order import SingleColumnOrder

FONT_SIZE = 9.0
LINE_PITCH = 11.0
LEFT_COLUMN = 108.0
RIGHT_COLUMN = 330.0
COLUMN_TOP_BASELINE = 110.0
SPANNING_OPENING_BASELINE = 200.0
FIRST_ENTRY = ["First entry of the list."]
SECOND_ENTRY = ["Second entry of the list sits", "in the left column below the", "first entry and runs down."]
SPANNING_ENTRY_ON_THE_LEFT = ["Third entry opens low on the", "left and carries on at the",
                              "top of the right column so"]
SPANNING_ENTRY_ON_THE_RIGHT = ["that its box reaches above", "the first entry on the left", "and holds both columns at",
                               "once in one engine block."]
FIRST_ENTRY_BOX = (106.0, 97.0, 300.0, 113.0)
SECOND_ENTRY_BOX = (106.0, 123.0, 300.0, 157.0)
SPANNING_ENTRY_BOX = (106.0, 100.0, 520.0, 225.0)
FIRST_ENTRY_ID = "/page/1/Text/0"
EMPTY_TWIN_ID = "/page/1/Text/1"
SECOND_ENTRY_ID = "/page/1/Text/2"
SPANNING_ENTRY_ID = "/page/1/Text/3"


class TwoColumnListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            self._column(page, FIRST_ENTRY + [""] + SECOND_ENTRY, (LEFT_COLUMN, COLUMN_TOP_BASELINE))
            self._column(page, SPANNING_ENTRY_ON_THE_LEFT, (LEFT_COLUMN, SPANNING_OPENING_BASELINE))
            self._column(page, SPANNING_ENTRY_ON_THE_RIGHT, (RIGHT_COLUMN, COLUMN_TOP_BASELINE))
            document.save(self._path)
        return self._path

    @staticmethod
    def _column(page, lines: list[str], origin: tuple[float, float]) -> None:
        left, first_baseline = origin
        for row, text in enumerate(lines):
            page.insert_text((left, first_baseline + row * LINE_PITCH), text, fontname="helv", fontsize=FONT_SIZE)


def block(box: tuple, identifier: str) -> Block:
    return Block(1, TEXT_KIND, "", box, {}, identifier)


class TestSingleColumnOrderOfTwoColumnBlocks(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(TwoColumnListPdf(directory / "columns.pdf").write())
        self.addCleanup(self._layer.close)

    def _ordered(self, blocks: list[Block]) -> list[str]:
        ordered = SingleColumnOrder(PageLines(self._layer, 1, blocks)).ordered(blocks)
        return [held.identifier for held in ordered]

    def test_a_block_whose_lines_form_two_columns_is_ordered_by_the_top_of_its_first_column(self) -> None:
        blocks = [block(SPANNING_ENTRY_BOX, SPANNING_ENTRY_ID), block(FIRST_ENTRY_BOX, FIRST_ENTRY_ID),
                  block(SECOND_ENTRY_BOX, SECOND_ENTRY_ID)]
        self.assertEqual([FIRST_ENTRY_ID, SECOND_ENTRY_ID, SPANNING_ENTRY_ID], self._ordered(blocks))

    def test_an_empty_block_sharing_a_one_column_blocks_box_keeps_its_place_behind_it(self) -> None:
        blocks = [block(FIRST_ENTRY_BOX, FIRST_ENTRY_ID), block(FIRST_ENTRY_BOX, EMPTY_TWIN_ID),
                  block(SECOND_ENTRY_BOX, SECOND_ENTRY_ID), block(SPANNING_ENTRY_BOX, SPANNING_ENTRY_ID)]
        self.assertEqual([FIRST_ENTRY_ID, EMPTY_TWIN_ID, SECOND_ENTRY_ID, SPANNING_ENTRY_ID], self._ordered(blocks))


if __name__ == "__main__":
    unittest.main()
