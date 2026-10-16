from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import Block
from _extract.layer import TextLayer
from _extract.layerlines import PageLines

LIST_ITEM_KIND = "ListItem"
TEXT_KIND = "Text"
FONT = "helv"
FONT_SIZE = 10.0
LEFT = 72.0
RIGHT = 400.0
FIRST_BASELINE = 100.0
LINE_PITCH = 13.0
ABOVE_BASELINE = 10.0
SHORT_OF_THE_NEXT_BASELINE = 2.0
BELOW_THE_LAST_BASELINE = 3.0
ITEMS = [["one: a probabilistic test renders it likely that a number is prime;"],
         ["two: numeric simulations render it plausible that it is true;"],
         ["three: formal verification renders it nearly certain that it has a correct", "proof."]]


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class ListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        lines = [line for item in ITEMS for line in item]
        with pymupdf.open() as document:
            page = document.new_page()
            for row, line in enumerate(lines):
                page.insert_text((LEFT, baseline_of(row)), line, fontname=FONT, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def item_blocks() -> list[Block]:
    blocks, row = [], 0
    for number, item in enumerate(ITEMS):
        last_row = row + len(item) - 1
        is_last = number == len(ITEMS) - 1
        bottom = (baseline_of(last_row) + BELOW_THE_LAST_BASELINE if is_last
                  else baseline_of(last_row + 1) - SHORT_OF_THE_NEXT_BASELINE)
        box = (LEFT, baseline_of(row) - ABOVE_BASELINE, RIGHT, bottom)
        blocks.append(Block(1, LIST_ITEM_KIND, "", box, {}, f"/page/1/ListItem/{number}"))
        row = last_row + 1
    return blocks


def text_block_over_a_wrapped_item() -> list[Block]:
    opening_row = len(ITEMS) - 1
    wrap_row = opening_row + 1
    text_box = (LEFT, baseline_of(opening_row) - ABOVE_BASELINE, RIGHT,
                baseline_of(wrap_row) - SHORT_OF_THE_NEXT_BASELINE)
    item_box = (LEFT, baseline_of(opening_row) - SHORT_OF_THE_NEXT_BASELINE, RIGHT,
                baseline_of(wrap_row) + ABOVE_BASELINE)
    return [Block(1, TEXT_KIND, "", text_box, {}, "/page/1/Text/0"),
            Block(1, LIST_ITEM_KIND, "", item_box, {}, "/page/1/ListItem/0")]


def owned_rows(blocks: list[Block]) -> list[list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(ListPdf(Path(directory) / "list.pdf").write())
        try:
            lines = PageLines(layer, 1, blocks)
            return [["".join(char.char for char in row).strip() for row in lines.of(block)] for block in blocks]
        finally:
            layer.close()


class TestListItemsWhoseBoxesReachIntoTheNextItemsLine(unittest.TestCase):
    def test_each_line_belongs_to_the_item_holding_all_of_it(self) -> None:
        self.assertEqual(ITEMS, owned_rows(item_blocks()))

    def test_a_line_a_smaller_block_of_another_kind_holds_in_part_still_belongs_to_the_smaller_block(self) -> None:
        self.assertEqual([ITEMS[-1], []], owned_rows(text_block_over_a_wrapped_item()))

if __name__ == "__main__":
    unittest.main()
