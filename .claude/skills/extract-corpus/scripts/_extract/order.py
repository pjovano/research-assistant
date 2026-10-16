from __future__ import annotations

from _extract.blocks import FOOTNOTE_KIND, Block
from _extract.layerlines import PageLines


class SingleColumnOrder:
    def __init__(self, lines: PageLines) -> None:
        self._lines = lines

    def ordered(self, blocks: list[Block]) -> list[Block]:
        content = [block for block in blocks if not block.is_furniture]
        if not self._reads_as_one_column([block for block in content if self._sets_the_column(block)]):
            return blocks
        furniture = [block for block in blocks if block.is_furniture]
        notes = _NoteColumns([block for block in content if block.kind == FOOTNOTE_KIND])
        return furniture + notes.placed(sorted(content, key=self._lines.opening_top))

    def _sets_the_column(self, block: Block) -> bool:
        return block.kind != FOOTNOTE_KIND and not self._lines.lies_beside_the_column(block)

    @staticmethod
    def _reads_as_one_column(content: list[Block]) -> bool:
        return all(first.bbox.shares_a_column_with(second.bbox)
                   for index, first in enumerate(content) for second in content[index + 1:])


class _NoteColumns:
    def __init__(self, notes: list[Block]) -> None:
        self._columns = _side_by_side(notes)

    def placed(self, ordered: list[Block]) -> list[Block]:
        later = {block.identifier for column in self._columns[1:] for block in column}
        placed = [block for block in ordered if block.identifier not in later]
        for previous, column in zip(self._columns, self._columns[1:]):
            placed = _inserted_after(placed, previous, [block for block in ordered if block in column])
        return placed


def _side_by_side(notes: list[Block]) -> list[list[Block]]:
    columns: list[list[Block]] = []
    for note in sorted(notes, key=lambda block: block.bbox.left):
        if columns and note.bbox.left < max(block.bbox.right for block in columns[-1]):
            columns[-1].append(note)
        else:
            columns.append([note])
    return columns


def _inserted_after(placed: list[Block], previous: list[Block], column: list[Block]) -> list[Block]:
    after = max(index for index, block in enumerate(placed) if block in previous) + 1
    return placed[:after] + column + placed[after:]
