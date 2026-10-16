from __future__ import annotations

import statistics
from dataclasses import dataclass

from _extract.blocks import LIST_GROUP_KIND, LIST_ITEM_KIND, TEXT_KIND, Block
from _extract.layerlines import MARGINAL_REFERENCE_RE, PageLines, box_of, left_of
from _extract.lists import BLANK_LINE_PITCHES, MARGIN_TOLERANCE_POINTS
from _extract.sentences import closes_a_sentence

FULL_LINE_SHARE = 0.9
CLOSING_KINDS = (TEXT_KIND, LIST_GROUP_KIND, LIST_ITEM_KIND)


@dataclass(frozen=True)
class WorkLayout:
    indents_openings: bool = False
    row_widths: tuple[float, ...] = ()

    def after(self, page: ParagraphIndents) -> WorkLayout:
        widest = page.widest_row()
        widths = self.row_widths + ((widest,) if widest is not None else ())
        return WorkLayout(self.indents_openings or page.indents_openings(), widths)


class ParagraphIndents:
    def __init__(self, lines: PageLines, blocks: list[Block], work: WorkLayout = WorkLayout()) -> None:
        self._rows = {block.identifier: lines.of(block) for block in blocks if block.kind == TEXT_KIND}
        self._closing_rows = {block.identifier: lines.of(block) for block in blocks if block.kind in CLOSING_KINDS}
        self._previous = {block.identifier: previous for previous, block in zip([None, *blocks], blocks)}
        self._column_left = min((left_of(row) for rows in self._rows.values() for row in rows), default=0.0)
        self._work = work

    def indents_openings(self) -> bool:
        return any(self._opens_indented(rows) for rows in self._rows.values())

    def widest_row(self) -> float | None:
        return max((_width_of(rows) for rows in self._rows.values() if rows), default=None)

    def resumes(self, block: Block) -> bool:
        rows = self._rows.get(block.identifier) or []
        indented_elsewhere = self._work.indents_openings or self._indents_openings_besides(block)
        opens_flush = bool(rows) and self._is_flush(rows[0]) and indented_elsewhere
        return opens_flush and not (self._follows_a_closed_line(block) or self._stands_a_blank_line_below(block))

    def _stands_a_blank_line_below(self, block: Block) -> bool:
        above = self._rows_above(block)
        rows = self._rows.get(block.identifier) or []
        pitches = _row_pitches(above) + _row_pitches(rows)
        if not (above and rows and pitches):
            return False
        gap = _center_of(rows[0]) - _center_of(above[-1])
        return gap >= BLANK_LINE_PITCHES * statistics.median(pitches)

    def _rows_above(self, block: Block) -> list[list]:
        previous = self._previous.get(block.identifier)
        return (self._closing_rows.get(previous.identifier) if previous is not None else None) or []

    def openings(self, block: Block) -> list[int]:
        rows = self._rows.get(block.identifier) or []
        indented = [position for position in range(1, len(rows)) if self._sets_its_text_indented(rows[position])]
        opening = [position for position in indented if closes_a_sentence(_text_of(rows[position - 1]))]
        opens_at_the_indent = len(opening) > len(indented) / 2
        return opening if opens_at_the_indent and self._indents_paragraph_openings() else []

    def _sets_its_text_indented(self, row: list) -> bool:
        return not self._is_flush(_text_beside_its_mark(row))

    def _indents_paragraph_openings(self) -> bool:
        return self._work.indents_openings or self.indents_openings()

    def _follows_a_closed_line(self, block: Block) -> bool:
        rows = self._rows_above(block)
        measure = self._measure()
        if not rows or measure is None:
            return False
        last_row_reach = box_of(rows[-1]).right - min(left_of(row) for row in rows)
        return last_row_reach < FULL_LINE_SHARE * measure

    def _measure(self) -> float | None:
        widest = self.widest_row()
        widths = self._work.row_widths + ((widest,) if widest is not None else ())
        return statistics.median(widths) if widths else None

    def _indents_openings_besides(self, block: Block) -> bool:
        return any(self._opens_indented(rows) for identifier, rows in self._rows.items()
                   if identifier != block.identifier)

    def _opens_indented(self, rows: list[list]) -> bool:
        return len(rows) > 1 and not self._is_flush(rows[0]) and any(self._is_flush(row) for row in rows[1:])

    def _is_flush(self, row: list) -> bool:
        return left_of(row) <= self._column_left + MARGIN_TOLERANCE_POINTS


def _row_pitches(rows: list[list]) -> list[float]:
    return [_center_of(lower) - _center_of(upper) for upper, lower in zip(rows, rows[1:])]


def _center_of(row: list) -> float:
    return box_of(row).center[1]


def _text_of(row: list) -> str:
    return "".join(char.char for char in row)


def _text_beside_its_mark(row: list) -> list:
    leading_line = [char for char in row if char.line == row[0].line]
    text = [char for char in row if char.line != row[0].line]
    is_a_mark = MARGINAL_REFERENCE_RE.match(_text_of(leading_line).strip()) is not None
    return text if text and is_a_mark else row


def _width_of(rows: list[list]) -> float:
    left = min(left_of(row) for row in rows)
    return max(box_of(row).right for row in rows) - left
