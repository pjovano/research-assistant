from __future__ import annotations

import statistics

from _extract.blocks import LIST_GROUP_KIND, LIST_ITEM_KIND, TEXT_KIND, Block
from _extract.lists import MARGIN_TOLERANCE_POINTS

PROSE_KINDS = (TEXT_KIND, LIST_GROUP_KIND, LIST_ITEM_KIND)


class IndentedDisplays:
    def __init__(self, content: list[Block]) -> None:
        self._prose = [block for block in content if block.kind in PROSE_KINDS]

    def hold(self, block: Block) -> bool:
        column = [other for other in self._prose if other.bbox.left <= block.bbox.center[0] <= other.bbox.right]
        if not column:
            return False
        column_left = statistics.median(other.bbox.left for other in column)
        return any(_is_inset_from(neighbour, column_left) and _shares_the_left_edge_of(neighbour, block)
                   for neighbour in _neighbours_of(block, column))


def _neighbours_of(block: Block, column: list[Block]) -> list[Block]:
    middle = block.bbox.center[1]
    above = [other for other in column if other.bbox.center[1] < middle]
    below = [other for other in column if other.bbox.center[1] > middle]
    nearest_above = [max(above, key=lambda other: other.bbox.center[1])] if above else []
    nearest_below = [min(below, key=lambda other: other.bbox.center[1])] if below else []
    return nearest_above + nearest_below


def _is_inset_from(block: Block, column_left: float) -> bool:
    return block.bbox.left - column_left > MARGIN_TOLERANCE_POINTS


def _shares_the_left_edge_of(block: Block, other: Block) -> bool:
    return abs(block.bbox.left - other.bbox.left) <= MARGIN_TOLERANCE_POINTS
