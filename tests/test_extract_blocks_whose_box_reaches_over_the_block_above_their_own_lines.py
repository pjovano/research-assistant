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

FONT_SIZE = 10.0
LINE_PITCH = 11.0
LEFT = 72.0
RIGHT = 520.0
FIRST_BASELINE = 110.0
ITEM_LINES = ("iv) Recognitional concepts are perspectival, as the creatures seen up close",
              "and those seen at a distance show; a concept can be ascribed outside its",
              "constitutive perspective. This plays a key role")
CLOSING_LINE = "below in the account of third-person ascriptions."
PARAGRAPH_LINES = ("The next paragraph opens a new thought and runs on for a line",
                   "below the list it follows.")
REACH_ABOVE = 3.0
HALF_LINE = 5.0
ITEM_ID = "/page/1/ListItem/0"
CLOSING_ID = "/page/1/Text/1"
PARAGRAPH_ID = "/page/1/Text/2"


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


CLOSING_ROW = len(ITEM_LINES)
PARAGRAPH_ROW = CLOSING_ROW + 2
ITEM_BOX = (LEFT, _baseline(0) - FONT_SIZE, RIGHT, _baseline(CLOSING_ROW - 1) + HALF_LINE / 2)
CLOSING_BOX_REACHING_OVER_THE_ITEM = (LEFT - REACH_ABOVE, ITEM_BOX[1] - REACH_ABOVE, RIGHT + REACH_ABOVE,
                                      _baseline(CLOSING_ROW) + HALF_LINE)
PARAGRAPH_BOX = (LEFT, _baseline(PARAGRAPH_ROW) - FONT_SIZE, RIGHT,
                 _baseline(PARAGRAPH_ROW + len(PARAGRAPH_LINES) - 1) + HALF_LINE)


class ListItemWithClosingLinePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        printed = [*ITEM_LINES, CLOSING_LINE, "", *PARAGRAPH_LINES]
        with pymupdf.open() as document:
            page = document.new_page()
            for row, text in enumerate(printed):
                page.insert_text((LEFT, _baseline(row)), text, fontname="helv", fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def block(box: tuple, identifier: str) -> Block:
    return Block(1, TEXT_KIND, "", box, {}, identifier)


class TestBlocksWhoseBoxReachesOverTheBlockAboveTheirOwnLines(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(ListItemWithClosingLinePdf(directory / "item.pdf").write())
        self.addCleanup(self._layer.close)

    def _ordered(self, blocks: list[Block]) -> list[str]:
        ordered = SingleColumnOrder(PageLines(self._layer, 1, blocks)).ordered(blocks)
        return [held.identifier for held in ordered]

    def test_a_block_reaching_over_the_item_above_its_closing_line_follows_the_item(self) -> None:
        blocks = [block(ITEM_BOX, ITEM_ID), block(CLOSING_BOX_REACHING_OVER_THE_ITEM, CLOSING_ID),
                  block(PARAGRAPH_BOX, PARAGRAPH_ID)]
        self.assertEqual([ITEM_ID, CLOSING_ID, PARAGRAPH_ID], self._ordered(blocks))

    def test_a_block_reaching_over_the_item_follows_it_whichever_the_engine_lists_first(self) -> None:
        blocks = [block(CLOSING_BOX_REACHING_OVER_THE_ITEM, CLOSING_ID), block(PARAGRAPH_BOX, PARAGRAPH_ID),
                  block(ITEM_BOX, ITEM_ID)]
        self.assertEqual([ITEM_ID, CLOSING_ID, PARAGRAPH_ID], self._ordered(blocks))


if __name__ == "__main__":
    unittest.main()
