from __future__ import annotations

from _extract.blocks import Block
from _extract.footnotes import leading_note_number
from _extract.layerlines import PageLines, box_of, row_text
from _extract.strays import STACKED_OVERLAP_POINTS


class OverlappingNotes:
    def __init__(self, lines: PageLines, marks: set[str]) -> None:
        self._lines = lines
        self._marks = marks

    def grouped(self, blocks: list[Block]) -> list[list[Block]]:
        groups: list[list[Block]] = []
        for block in blocks:
            overlapped = [group for group in groups if self._overlaps_any(block, group)]
            merged = [held for group in overlapped for held in group] + [block]
            groups = [group for group in groups if group not in overlapped] + [merged]
        order = {block.identifier: index for index, block in enumerate(blocks)}
        ordered = [sorted(group, key=lambda held: order[held.identifier]) for group in groups]
        return sorted(ordered, key=lambda group: order[group[0].identifier])

    def notes_of(self, group: list[Block]) -> list[list[list]]:
        notes: list[list[list]] = []
        for row, opens_a_block in self._rows_in_page_order(group):
            if notes and not self._opens_a_note(row, opens_a_block):
                notes[-1].append(row)
            else:
                notes.append([row])
        return notes

    def _overlaps_any(self, block: Block, group: list[Block]) -> bool:
        return self._holds_rows(block) and any(self._holds_rows(held) and _overlap(block, held) for held in group)

    def _holds_rows(self, block: Block) -> bool:
        return bool(self._lines.of(block))

    def _rows_in_page_order(self, group: list[Block]) -> list[tuple[list, bool]]:
        rows = [(row, index == 0) for block in group for index, row in enumerate(self._lines.of(block))]
        is_one_reading = len(group) == 1
        return rows if is_one_reading else sorted(rows, key=lambda held: box_of(held[0]).top)

    def _opens_a_note(self, row: list, opens_a_block: bool) -> bool:
        number = leading_note_number(row_text(row))
        return number is not None and (opens_a_block or number in self._marks)


def _overlap(block: Block, other: Block) -> bool:
    box, held = block.bbox, other.bbox
    shared_height = min(box.bottom, held.bottom) - max(box.top, held.top)
    return box.shares_a_column_with(held) and shared_height > STACKED_OVERLAP_POINTS
