from __future__ import annotations

import dataclasses

from _extract.blocks import CAPTION_KIND, FOOTNOTE_KIND, HEADING_KIND, TABLE_KIND, Block
from _extract.box import Box
from _extract.layerlines import PageLines
from _extract.strays import STACKED_OVERLAP_POINTS


class EngineTwins:
    def __init__(self, blocks: list[Block]) -> None:
        self._content = [block for block in FigurelessCaptions(blocks).headed() if not block.is_furniture]

    def without(self, blocks: list[Block]) -> list[Block]:
        headed = FigurelessCaptions(blocks).headed()
        return [block for block in headed if not any(self._yields_to(block, twin) for twin in self._twins_of(block))]

    def _twins_of(self, block: Block) -> list[Block]:
        twins = [other for other in self._content if other is not block and self._read_twice(block, other)]
        return twins + self._straddled_by(block)

    def _straddled_by(self, block: Block) -> list[Block]:
        if block.plain_text:
            return []
        read = [other for other in self._content
                if other.kind == block.kind and other.plain_text and _overlaps(block.bbox, other.bbox)]
        if not read or not _lies_within_all(block.bbox, [other.bbox for other in read]):
            return []
        return read

    @staticmethod
    def _read_twice(block: Block, other: Block) -> bool:
        one_left_empty = not block.plain_text or not other.plain_text
        if other.kind == block.kind:
            return one_left_empty and (_lies_within(block, other) or _lies_within(other, block))
        return one_left_empty and block.bbox.shares_a_region_with(other.bbox)

    @staticmethod
    def _yields_to(block: Block, twin: Block) -> bool:
        if HEADING_KIND in (block.kind, twin.kind) and block.kind != twin.kind:
            return block.kind == HEADING_KIND
        keeps_the_notes_judgment = block.kind == FOOTNOTE_KIND and twin.kind != FOOTNOTE_KIND
        return not keeps_the_notes_judgment and not block.plain_text and bool(twin.plain_text)


class FigurelessCaptions:
    def __init__(self, blocks: list[Block]) -> None:
        self._blocks = blocks
        self._accompanied = any(block.is_image or block.kind == TABLE_KIND for block in blocks)

    def headed(self) -> list[Block]:
        if self._accompanied:
            return self._blocks
        return [self._headed(block) for block in self._blocks]

    def _headed(self, block: Block) -> Block:
        if block.kind == CAPTION_KIND and self._is_read_as_an_empty_heading_too(block):
            return dataclasses.replace(block, kind=HEADING_KIND)
        return block

    def _is_read_as_an_empty_heading_too(self, caption: Block) -> bool:
        return any(other.kind == HEADING_KIND and not other.plain_text and other.bbox.shares_a_region_with(caption.bbox)
                   for other in self._blocks)


class NoteTwins:
    def __init__(self, lines: PageLines) -> None:
        self._lines = lines

    def without(self, blocks: list[Block]) -> list[Block]:
        return [block for block in blocks if not self._rereads_notes(block, blocks)]

    def _rereads_notes(self, block: Block, blocks: list[Block]) -> bool:
        if block.kind == FOOTNOTE_KIND or block.is_furniture or self._lines.of(block):
            return False
        holders = [other for other in blocks
                   if other is not block and _box_lies_within(other.bbox, block.bbox) and self._lines.of(other)]
        return bool(holders) and all(holder.kind == FOOTNOTE_KIND for holder in holders)


def _lies_within(inner: Block, outer: Block) -> bool:
    return _box_lies_within(inner.bbox, outer.bbox)


def _box_lies_within(box: Box, around: Box) -> bool:
    horizontally = (around.left - STACKED_OVERLAP_POINTS <= box.left
                    and box.right <= around.right + STACKED_OVERLAP_POINTS)
    vertically = (around.top - STACKED_OVERLAP_POINTS <= box.top
                  and box.bottom <= around.bottom + STACKED_OVERLAP_POINTS)
    return horizontally and vertically


def _lies_within_all(box: Box, around: list[Box]) -> bool:
    return _box_lies_within(box, Box.union(around)) and _covered_without_a_gap(box, around)


def _covered_without_a_gap(box: Box, around: list[Box]) -> bool:
    reached = box.top
    for other in sorted(around, key=lambda candidate: candidate.top):
        if other.top - STACKED_OVERLAP_POINTS > reached:
            return False
        reached = max(reached, other.bottom)
    return reached + STACKED_OVERLAP_POINTS >= box.bottom


def _overlaps(box: Box, other: Box) -> bool:
    return box.shares_a_column_with(other) and box.top < other.bottom and other.top < box.bottom
