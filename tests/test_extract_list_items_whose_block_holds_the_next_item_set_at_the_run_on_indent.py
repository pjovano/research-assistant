from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import LIST_ITEM_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Verbatim

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
LINE_PITCH = 12.0
FIRST_BASELINE = 100.0
ABOVE_BASELINE = 9.0
BELOW_BASELINE = 3.0
MARGIN = 54.0
RUN_ON_INDENT = 66.0
NUMBER_GAP = 24.0
RIGHT = 390.0
PAGE_WIDTH, PAGE_HEIGHT = 440.0, 600.0
SUBLEVEL = 2
FIRST_ITEM = [(MARGIN, "1. If the conditions settle how a person acts at a time,"),
              (RUN_ON_INDENT, "then the act that person performs is not free.")]
LATER_ITEMS = [(MARGIN, "2. If the conditions do not settle how a person acts at a time,"),
               (RUN_ON_INDENT, "then the act that person performs is not free."),
               (RUN_ON_INDENT, "3."),
               (RUN_ON_INDENT + NUMBER_GAP, "If the acts of a person are never free, then the"),
               (RUN_ON_INDENT, "consequences of those acts are not that person's.")]
ROWS_OF_LATER_ITEMS = [0, 1, 2, 2, 3]
FIRST_ITEM_TEXT = "1. If the conditions settle how a person acts at a time, then the act that person performs is not free."
SECOND_ITEM_TEXT = ("2. If the conditions do not settle how a person acts at a time, then the act that person performs "
                    "is not free.")
THIRD_ITEM_TEXT = "3. If the acts of a person are never free, then the consequences of those acts are not that person's."


def baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class NumberedListPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        placed = [(left, text, row) for row, (left, text) in enumerate(FIRST_ITEM)]
        later_first_row = len(FIRST_ITEM)
        placed += [(left, text, later_first_row + row) for (left, text), row in zip(LATER_ITEMS, ROWS_OF_LATER_ITEMS)]
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for left, text, row in placed:
                page.insert_text((left, baseline(row)), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def item_block(rows: tuple[int, int], html: str, number: int) -> Block:
    first_row, last_row = rows
    box = (MARGIN, baseline(first_row) - ABOVE_BASELINE, RIGHT, baseline(last_row) + BELOW_BASELINE)
    return Block(FILE_PAGE, LIST_ITEM_KIND, f"<li>{html}</li>", box, {}, f"/page/{FILE_PAGE}/ListItem/{number}")


def engine_blocks() -> list[Block]:
    later_first_row = len(FIRST_ITEM)
    later_last_row = later_first_row + ROWS_OF_LATER_ITEMS[-1]
    nested = f"{SECOND_ITEM_TEXT} <ul><li>{THIRD_ITEM_TEXT}</li></ul>"
    return [item_block((0, later_first_row - 1), FIRST_ITEM_TEXT, 0),
            item_block((later_first_row, later_last_row), nested, 1)]


class TestListItemsWhoseBlockHoldsTheNextItemSetAtTheRunOnIndent(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "list.pdf"

    def items(self) -> list[str]:
        layer = TextLayer(NumberedListPdf(self._path).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(PageBlocks(FILE_PAGE, engine_blocks()), [], SUBLEVEL).elements
        return [element.text for element in elements if isinstance(element, Verbatim)]

    def test_a_row_opening_on_the_next_number_inside_an_items_block_opens_an_item_of_its_own(self) -> None:
        self.assertEqual([f"- {FIRST_ITEM_TEXT}", f"- {SECOND_ITEM_TEXT}", f"- {THIRD_ITEM_TEXT}"], self.items())


if __name__ == "__main__":
    unittest.main()
