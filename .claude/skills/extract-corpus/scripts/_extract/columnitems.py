from __future__ import annotations

import re

from _extract.blocks import Block
from _extract.layer import LayerLine
from _extract.lists import HangingIndentList

OPENING_WORDS = 3
_UNCOMPARED_RE = re.compile(r"[\W_]+")


class ColumnItemOrder:
    def __init__(self, lists: HangingIndentList) -> None:
        self._lists = lists

    def ordered(self, block: Block, items: list[str]) -> list[str]:
        columns = self._lists.columns(block.file_page, [block.bbox])
        if len(columns) < 2 or len(items) < 2:
            return items
        placed = _ItemColumns(columns).of(items)
        if placed is None or placed == sorted(placed):
            return items
        return [item for _column, item in sorted(zip(placed, items), key=lambda pair: pair[0])]


class _ItemColumns:
    def __init__(self, columns: list[list[LayerLine]]) -> None:
        self._openings = [[_comparable(line.text) for line in column] for column in columns]

    def of(self, items: list[str]) -> list[int] | None:
        placed: list[int] = []
        for item in items:
            column = self._column_opening(item)
            if column is None and not placed:
                return None
            placed.append(placed[-1] if column is None else column)
        return placed

    def _column_opening(self, item: str) -> int | None:
        opening = _comparable(" ".join(item.split()[:OPENING_WORDS]))
        if not opening:
            return None
        found = [index for index, lines in enumerate(self._openings) if any(line.startswith(opening) for line in lines)]
        return found[0] if len(found) == 1 else None


def _comparable(text: str) -> str:
    return _UNCOMPARED_RE.sub("", text.casefold())
