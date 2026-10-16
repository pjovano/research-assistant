from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.layerlines import PageLines
from _extract_fixtures import BODY_SIZE, FakeLayer, RunSetting, positioned

PAGE_BOX = (0.0, 0.0, 500.0, 300.0)
CAPITAL_LEFT = 60.0
COLUMN_LEFT = 90.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
DROPPED_SIZE = BODY_SIZE * 2
OPENED = "ollowing the argument, the reader is asked to look once more"
SECOND = "again at the text and at its claims about human cognition"


def page_block() -> Block:
    return Block(1, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/0")


def row_texts(chars: list) -> list[str]:
    rows = PageLines(FakeLayer(chars), 1, [page_block()]).of(page_block())
    return ["".join(char.char for char in row) for row in rows]


def body_line(text: str, row: int, line: int) -> list:
    return positioned(text, RunSetting(COLUMN_LEFT, FIRST_BASELINE + row * LINE_PITCH, line))


def capital(line: int) -> list:
    return positioned("F", RunSetting(CAPITAL_LEFT, FIRST_BASELINE + LINE_PITCH, line, size=DROPPED_SIZE))


class TestDropCapitalsBesideLinesEachOpeningWithABlank(unittest.TestCase):
    def test_the_blank_every_line_beside_the_capital_opens_with_is_dropped_from_the_word_it_opens(self) -> None:
        chars = body_line(f" {OPENED}", 0, 0) + body_line(f" {SECOND}", 1, 1) + capital(2)
        self.assertEqual(f"F{OPENED}", row_texts(chars)[0])

    def test_a_blank_only_the_opened_line_opens_with_stays_a_word_gap(self) -> None:
        chars = body_line(f" {OPENED}", 0, 0) + body_line(SECOND, 1, 1) + capital(2)
        self.assertEqual(f"F {OPENED}", row_texts(chars)[0])


if __name__ == "__main__":
    unittest.main()
