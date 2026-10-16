from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.layerlines import PageLines
from _extract_fixtures import BODY_SIZE, FakeLayer, RunSetting, positioned

PAGE_BOX = (0.0, 0.0, 500.0, 300.0)
MARGIN_LEFT = 60.0
SIDE_BEARING = 0.5
INDENTED_LEFT = 95.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
CAPITAL_SIZE = BODY_SIZE * 3
DROPPED_ROWS = 3
OPENED = "ecent translations of the works of Kant contain pagina-"
SECOND = "tion from their critical German editions and references"
THIRD = "to the pages of the English translations are provided"
FLUSH = "only when the translation does not contain the pagination"


def page_block() -> Block:
    return Block(1, TEXT_KIND, "", PAGE_BOX, {}, "/page/1/Text/0")


def row_texts(chars: list) -> list[str]:
    rows = PageLines(FakeLayer(chars), 1, [page_block()]).of(page_block())
    return ["".join(char.char for char in row) for row in rows]


def baseline_of_row(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class TestDropCapitalsAboveALineSetFlushWithTheMargin(unittest.TestCase):
    def test_the_capital_opens_the_first_line_it_drops_beside(self) -> None:
        indented = [positioned(text, RunSetting(INDENTED_LEFT, baseline_of_row(row), row))
                    for row, text in enumerate((OPENED, SECOND, THIRD))]
        flush = positioned(FLUSH, RunSetting(MARGIN_LEFT, baseline_of_row(DROPPED_ROWS), DROPPED_ROWS))
        capital = positioned("R", RunSetting(MARGIN_LEFT + SIDE_BEARING, baseline_of_row(DROPPED_ROWS - 1),
                                             DROPPED_ROWS + 1, size=CAPITAL_SIZE))
        chars = [char for line in indented for char in line] + flush + capital
        self.assertEqual([f"R{OPENED}", SECOND, THIRD, FLUSH], row_texts(chars))


if __name__ == "__main__":
    unittest.main()
