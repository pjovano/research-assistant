from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.layerlines import PageLines, left_of

FILE_PAGE = 1
SUBLEVEL = 2
FONT = "helv"
BODY_SIZE = 10.0
MARGIN_SIZE = 8.0
NOTE_SIZE = 8.0
SMALL_CAPITALS_SIZE = 7.0
LEFT = 72.0
FIRST_BASELINE = 100.0
ROW_PITCH = 12.0
MARGIN_GAP = 12.0
PAGE_BOX = (0.0, 0.0, 612.0, 792.0)
NOTE_BASELINE = 700.0
LEFT_MARGIN = "left"
RIGHT_MARGIN = "right"
OPENING = ["The general character of the complaint against construing the faculties",
           "as instruments is that any such construal already presupposes a relation",
           "between the faculty and its objects, and so cannot open a critical enquiry."]
HYPHENATED = ["Such a construal presupposes a determinate and compre-",
              "hensive relation between the faculty and the objects it knows."]
CLOSING_REPLY = [("T", BODY_SIZE), ("HE", SMALL_CAPITALS_SIZE), (" S", BODY_SIZE), ("TRANGER", SMALL_CAPITALS_SIZE),
                 (": Agreed.", BODY_SIZE)]
NOTE = "1. Reading the manuscripts at this place, with the later editors."


@dataclass(frozen=True)
class MarginMark:
    text: str
    row: int
    side: str


class MarginedPage:
    def __init__(self, directory: Path, rows: list, marks: list[MarginMark]) -> None:
        self._path = directory / "margined.pdf"
        self._rows = [[(row, BODY_SIZE)] if isinstance(row, str) else row for row in rows]
        self._marks = marks

    def write(self, note: str = "") -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, row in enumerate(self._rows):
                self._draw(page, row, _baseline(index))
            for mark in self._marks:
                page.insert_text((self._mark_left(mark), _baseline(mark.row)), mark.text, fontsize=MARGIN_SIZE,
                                 fontname=FONT)
            if note:
                page.insert_text((LEFT, NOTE_BASELINE), note, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _draw(page, pieces: list[tuple[str, float]], baseline: float) -> None:
        left = LEFT
        for text, size in pieces:
            page.insert_text((left, baseline), text, fontsize=size, fontname=FONT)
            left += _width(text, size)

    def _mark_left(self, mark: MarginMark) -> float:
        if mark.side == LEFT_MARGIN:
            return LEFT - MARGIN_GAP - _width(mark.text, MARGIN_SIZE)
        column_right = max(LEFT + sum(_width(text, size) for text, size in row) for row in self._rows)
        return column_right + MARGIN_GAP


def _width(text: str, size: float) -> float:
    return pymupdf.get_text_length(text, fontname=FONT, fontsize=size)


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * ROW_PITCH


def whole_page_block() -> Block:
    return Block(FILE_PAGE, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/0")


class MarginedPageCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _layer(self, rows: list, marks: list[MarginMark], note: str = "") -> TextLayer:
        layer = TextLayer(MarginedPage(self._directory, rows, marks).write(note))
        self.addCleanup(layer.close)
        return layer

    def _texts(self, rows: list[str], marks: list[MarginMark]) -> list[str]:
        return self._assembled(self._layer(rows, marks), PageBlocks(FILE_PAGE, [whole_page_block()]))

    @staticmethod
    def _assembled(layer: TextLayer, blocks: PageBlocks) -> list[str]:
        assembler = page_assembler(layer, keep_everything())
        return [element.text for element in assembler.assemble(blocks, [], SUBLEVEL).elements[1:]]


class TestReferenceNumeralsSetInTheMarginBesideALine(MarginedPageCase):
    def test_a_numeral_set_small_in_the_outer_margin_opens_the_line_beside_it(self) -> None:
        texts = self._texts(OPENING, [MarginMark("127", 1, RIGHT_MARGIN)])
        self.assertEqual([f"{OPENING[0]} 127 {OPENING[1]} {OPENING[2]}"], texts)

    def test_a_numeral_set_small_in_the_inner_margin_opens_the_line_beside_it(self) -> None:
        texts = self._texts(OPENING, [MarginMark("126", 1, LEFT_MARGIN)])
        self.assertEqual([f"{OPENING[0]} 126 {OPENING[1]} {OPENING[2]}"], texts)

    def test_a_numeral_and_a_letter_each_open_the_line_beside_them(self) -> None:
        texts = self._texts(OPENING, [MarginMark("127", 1, RIGHT_MARGIN), MarginMark("b", 2, RIGHT_MARGIN)])
        self.assertEqual([f"{OPENING[0]} 127 {OPENING[1]} b {OPENING[2]}"], texts)


class TestMarginalNumeralsCountingThePagesLinesFromOne(MarginedPageCase):
    def test_numerals_counting_three_lines_from_one_are_dropped(self) -> None:
        marks = [MarginMark(str(row + 1), row, LEFT_MARGIN) for row in range(len(OPENING))]
        self.assertEqual([" ".join(OPENING)], self._texts(OPENING, marks))

    def test_numerals_counting_only_two_lines_from_one_are_kept(self) -> None:
        marks = [MarginMark("1", 0, LEFT_MARGIN), MarginMark("2", 1, LEFT_MARGIN)]
        self.assertEqual([f"1 {OPENING[0]} 2 {OPENING[1]} {OPENING[2]}"], self._texts(OPENING, marks))


class TestReferenceLettersBesideALineEndingInAHyphen(MarginedPageCase):
    def test_a_letter_beside_a_hyphenated_line_opens_that_line(self) -> None:
        texts = self._texts(HYPHENATED, [MarginMark("e", 0, RIGHT_MARGIN)])
        self.assertEqual(["e Such a construal presupposes a determinate and comprehensive relation between the "
                          "faculty and the objects it knows."], texts)

    def test_a_letter_beside_the_line_after_a_hyphenated_line_follows_the_joined_word(self) -> None:
        texts = self._texts(HYPHENATED, [MarginMark("e", 1, LEFT_MARGIN)])
        self.assertEqual(["Such a construal presupposes a determinate and comprehensive e relation between the "
                          "faculty and the objects it knows."], texts)


class TestLinesCarryingAMarginalReference(MarginedPageCase):
    def test_a_numeral_in_the_inner_margin_leaves_the_line_its_own_left_edge(self) -> None:
        layer = self._layer(OPENING, [MarginMark("126", 1, LEFT_MARGIN)])
        rows = PageLines(layer, FILE_PAGE, [whole_page_block()]).of(whole_page_block())
        self.assertAlmostEqual(LEFT, left_of(rows[1]), delta=1.0)

    def test_a_numeral_beside_a_short_closing_line_leaves_that_line_in_the_body(self) -> None:
        rows = OPENING + [CLOSING_REPLY]
        layer = self._layer(rows, [MarginMark("303", len(OPENING), RIGHT_MARGIN)], NOTE)
        texts = self._assembled(layer, PageBlocks(FILE_PAGE, _body_reply_and_note_blocks(len(OPENING))))
        self.assertIn("303 THE STRANGER: Agreed.", texts)


def _body_reply_and_note_blocks(reply_row: int) -> list[Block]:
    reply_top = _baseline(reply_row) - BODY_SIZE
    return [Block(FILE_PAGE, TEXT_KIND, "", (0.0, 0.0, 612.0, reply_top - 1.0), {}, "/page/1/Text/0"),
            Block(FILE_PAGE, TEXT_KIND, "", (0.0, reply_top, 612.0, reply_top + ROW_PITCH), {}, "/page/1/Text/1"),
            Block(FILE_PAGE, FOOTNOTE_KIND, "", (0.0, NOTE_BASELINE - NOTE_SIZE - 2.0, 612.0, NOTE_BASELINE + 4.0),
                  {}, "/page/1/Footnote/0")]


if __name__ == "__main__":
    unittest.main()
