from __future__ import annotations

from _extract.blocks import Block
from _extract.box import Box
from _extract.layerlines import PageLines, box_of, left_of

MIN_BULLETED_ROWS = 2
MAX_BULLET_GAP_SHARE = 2.0


class BulletedRows:
    def __init__(self, lines: PageLines | None, shapes: list[Box]) -> None:
        self._lines = lines
        self._shapes = shapes

    def openings(self, block: Block) -> list[int]:
        rows = self._lines.of(block) if self._lines is not None else []
        bulleted = [position for position, row in enumerate(rows) if self._has_a_bullet_beside(row)]
        opens_on_a_bullet = bool(bulleted) and bulleted[0] == 0
        return bulleted if opens_on_a_bullet and len(bulleted) >= MIN_BULLETED_ROWS else []

    def _has_a_bullet_beside(self, row: list) -> bool:
        return any(_stands_beside(shape, row) for shape in self._shapes)


def _stands_beside(shape: Box, row: list) -> bool:
    row_box, text_left = box_of(row), left_of(row)
    gap = text_left - shape.right
    on_the_row = row_box.top <= shape.center[1] <= row_box.bottom and shape.height <= row_box.height
    return on_the_row and 0 <= gap <= MAX_BULLET_GAP_SHARE * row_box.height
