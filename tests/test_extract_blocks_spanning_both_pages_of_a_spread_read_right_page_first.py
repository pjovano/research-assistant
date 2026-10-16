from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import LIST_GROUP_KIND, Block
from _extract.box import Box
from _extract.columnitems import ColumnItemOrder
from _extract.layer import TextLayer
from _extract.lists import HangingIndentList

FILE_PAGE = 1
FONT = "helv"
FONT_SIZE = 9.0
LINE_PITCH = 11.0
FIRST_BASELINE = 80.0
CHAPTER_OPENING_ROWS = 6
LEFT_PAGE_MARGIN = 46.0
RIGHT_PAGE_MARGIN = 444.0
HANGING_INDENT = 9.0
SPREAD_WIDTH, SPREAD_HEIGHT = 792.0, 610.0
SPREAD = Box(0.0, 0.0, SPREAD_WIDTH, SPREAD_HEIGHT)
LEFT_PAGE = [["Anderson, A. (1951). A note on subjunctive and counterfactual", "conditionals, Analysis 12: 35-8."],
             ["Aqvist, L. (1973). Modal logic with subjunctive conditionals and", "dispositional predicates."],
             ["Barwise, J., and Perry, J. (1983). Situations and Attitudes, MIT", "Press, Cambridge, Mass."],
             ["Belnap, N. (1970). Conditional assertion and restricted", "quantification, Nous 4: 1-13."]]
RIGHT_PAGE = [["De Sousa, R. (1971). How to give a piece of your mind: or, the", "logic of belief and assent."],
              ["Dennett, D. (1978). Brainstorms, Bradford Books, Montgomery,", "Vermont."],
              ["Donnellan, K. (1966). Reference and definite descriptions,", "Philosophical Review 75: 281-304."],
              ["Dretske, F. (1981). Knowledge and the Flow of Information, MIT", "Press, Cambridge, Mass."],
              ["Dummett, M. (1964). Bringing about the past, Philosophical", "Review 73: 338-9."],
              ["Evans, G. (1982). Varieties of Reference, Oxford University", "Press, Oxford and New York."],
              ["Fagin, R., and Halpern, J. Y. (1995). Reasoning about", "Knowledge, MIT Press, Cambridge, Mass."],
              ["Field, H. (1978). Mental representation, Erkenntnis 13:", "9-61."]]


def entry_texts(entries: list[list[str]]) -> list[str]:
    return [" ".join(lines) for lines in entries]


class SpreadPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=SPREAD_WIDTH, height=SPREAD_HEIGHT)
            self._page_entries(page, (LEFT_PAGE_MARGIN, CHAPTER_OPENING_ROWS), LEFT_PAGE)
            self._page_entries(page, (RIGHT_PAGE_MARGIN, 0), RIGHT_PAGE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _page_entries(page, start: tuple[float, int], entries: list[list[str]]) -> None:
        margin, row = start
        for opening, *run_on in entries:
            page.insert_text((margin, FIRST_BASELINE + row * LINE_PITCH), opening, fontsize=FONT_SIZE, fontname=FONT)
            for line in run_on:
                row += 1
                page.insert_text((margin + HANGING_INDENT, FIRST_BASELINE + row * LINE_PITCH), line,
                                 fontsize=FONT_SIZE, fontname=FONT)
            row += 1


class TestBlocksSpanningBothPagesOfASpreadReadRightPageFirst(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(SpreadPdf(Path(directory.name) / "spread.pdf").write())
        self.addCleanup(self.layer.close)
        self.lists = HangingIndentList(self.layer)

    def test_the_spreads_entries_read_the_left_page_before_the_right(self) -> None:
        entries = [" ".join(entry.split()) for entry in self.lists.entries(FILE_PAGE, SPREAD)]
        self.assertEqual(entry_texts(LEFT_PAGE) + entry_texts(RIGHT_PAGE), entries)

    def test_items_the_engine_reads_right_page_first_are_put_in_the_spreads_order(self) -> None:
        block = Block(FILE_PAGE, LIST_GROUP_KIND, "", SPREAD, {}, "/page/1/list")
        items = entry_texts(RIGHT_PAGE) + entry_texts(LEFT_PAGE)
        self.assertEqual(entry_texts(LEFT_PAGE) + entry_texts(RIGHT_PAGE), ColumnItemOrder(self.lists).ordered(block, items))

    def test_items_the_engine_reads_in_the_spreads_order_stay_in_it(self) -> None:
        block = Block(FILE_PAGE, LIST_GROUP_KIND, "", SPREAD, {}, "/page/1/list")
        items = entry_texts(LEFT_PAGE) + entry_texts(RIGHT_PAGE)
        self.assertEqual(items, ColumnItemOrder(self.lists).ordered(block, items))


if __name__ == "__main__":
    unittest.main()
