from __future__ import annotations

import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.layerlines import PageLines
from _extract_fixtures import ADVANCE, BODY_SIZE, FakeLayer, RunSetting, positioned

PAGE_BOX = (0.0, 0.0, 500.0, 300.0)
CAPITAL_LEFT = 60.0
COLUMN_LEFT = 90.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
DROPPED_SIZE = BODY_SIZE * 2
UNDROPPED_SIZE = BODY_SIZE * 1.4
OPENED = "ollowing the argument, the reader is asked to look once more"
SECOND = "again at the text and at its claims about human cognition"
THIRD = "before the second chapter takes up the question of spirit"


def page_block() -> Block:
    return Block(1, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/0")


def row_texts(chars: list) -> list[str]:
    rows = PageLines(FakeLayer(chars), 1, [page_block()]).of(page_block())
    return ["".join(char.char for char in row) for row in rows]


def body_line(text: str, row: int, line: int) -> list:
    return positioned(text, RunSetting(COLUMN_LEFT, FIRST_BASELINE + row * LINE_PITCH, line))


@dataclass(frozen=True)
class Capital:
    left: float = CAPITAL_LEFT
    size: float = DROPPED_SIZE


def capital(row: int, line: int, shape: Capital = Capital()) -> list:
    return positioned("F", RunSetting(shape.left, FIRST_BASELINE + row * LINE_PITCH, line, size=shape.size))


class TestDropCapitals(unittest.TestCase):
    def test_a_drop_capital_opens_the_first_line_it_drops_beside(self) -> None:
        chars = body_line(OPENED, 0, 0) + body_line(SECOND, 1, 1) + capital(1, 2)
        self.assertEqual([f"F{OPENED}", SECOND], row_texts(chars))

    def test_a_drop_capital_dropping_beside_three_lines_opens_the_first_of_them(self) -> None:
        chars = (body_line(OPENED, 0, 0) + body_line(SECOND, 1, 1) + body_line(THIRD, 2, 2)
                 + capital(2, 3, Capital(size=BODY_SIZE * 3)))
        self.assertEqual([f"F{OPENED}", SECOND, THIRD], row_texts(chars))

    def test_a_character_too_small_to_be_dropped_stays_in_the_line_it_shares_a_baseline_with(self) -> None:
        chars = body_line(OPENED, 0, 0) + body_line(SECOND, 1, 1) + capital(1, 2, Capital(size=UNDROPPED_SIZE))
        self.assertEqual([OPENED, f"F{SECOND}"], row_texts(chars))

    def test_a_dropped_character_set_right_of_the_lines_it_spans_stays_where_it_is(self) -> None:
        right = COLUMN_LEFT + len(SECOND) * ADVANCE
        chars = body_line(OPENED, 0, 0) + body_line(SECOND, 1, 1) + capital(1, 2, Capital(left=right))
        self.assertEqual([OPENED, f"{SECOND}F"], row_texts(chars))


if __name__ == "__main__":
    unittest.main()
