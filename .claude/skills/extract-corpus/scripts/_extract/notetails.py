from __future__ import annotations

import dataclasses
import statistics

from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block
from _extract.layerlines import PageLines, box_of_rows, paragraph_of_rows
from _extract.strays import NOTE_SIZE_TOLERANCE_POINTS, NOTE_TYPE_SHARE, STACKED_OVERLAP_POINTS
from _extract.typesizes import TypeSize

_BODY_SUFFIX = "/body"
_NOTE_TAIL_SUFFIX = "/note-tail"


class NoteTypeTails:
    def __init__(self, lines: PageLines, blocks: list[Block]) -> None:
        self._lines = lines
        notes = [block for block in blocks if block.kind == FOOTNOTE_KIND]
        self._notes_top = min((note.bbox.top for note in notes), default=None)
        sizes = [TypeSize(lines.of(note)).median() for note in notes]
        known = [size for size in sizes if size is not None]
        self._note_size = statistics.median(known) if known else None

    def parted(self, blocks: list[Block]) -> list[Block]:
        return [piece for block in blocks for piece in self._pieces(block)]

    def _pieces(self, block: Block) -> list[Block]:
        rows = self._lines.of(block)
        start = self._tail_start(rows) if block.kind == TEXT_KIND and self._note_size is not None else None
        if start is None:
            return [block]
        return [_body_piece(block, rows[:start]), _tail_piece(block, rows[start:])]

    def _tail_start(self, rows: list[list]) -> int | None:
        sizes = [TypeSize([row]).median() for row in rows]
        return next((start for start in range(1, len(rows))
                     if self._sets_notes_from(sizes, start) and self._reaches_the_notes(rows, start)), None)

    def _sets_notes_from(self, sizes: list[float | None], start: int) -> bool:
        body = [size for size in sizes[:start] if size is not None]
        tail = sizes[start:]
        if not body or None in tail:
            return False
        body_size = statistics.median(body)
        return all(size < NOTE_TYPE_SHARE * body_size and self._matches_the_notes(size) for size in tail)

    def _matches_the_notes(self, size: float) -> bool:
        return abs(size - self._note_size) <= NOTE_SIZE_TOLERANCE_POINTS

    def _reaches_the_notes(self, rows: list[list], start: int) -> bool:
        body, tail = box_of_rows(rows[:start]), box_of_rows(rows[start:])
        lies_below_the_body = tail.top >= body.bottom - STACKED_OVERLAP_POINTS
        return lies_below_the_body and tail.bottom <= self._notes_top + STACKED_OVERLAP_POINTS


def _body_piece(block: Block, rows: list[list]) -> Block:
    return dataclasses.replace(_piece(block, rows, _BODY_SUFFIX), continued=block.continues)


def _tail_piece(block: Block, rows: list[list]) -> Block:
    return _piece(block, rows, _NOTE_TAIL_SUFFIX)


def _piece(block: Block, rows: list[list], suffix: str) -> Block:
    return dataclasses.replace(block, html=paragraph_of_rows(rows), bbox=box_of_rows(rows),
                               identifier=f"{block.identifier}{suffix}", continued=False)
