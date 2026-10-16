from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import zip_longest

from _extract.blocks import (
    FURNITURE_KINDS, HEADING_KIND, LIST_ITEM_KIND, TABLE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks,
)
from _extract.box import Box
from _extract.layercolumns import MIN_GUTTER_POINTS
from _extract.layerlines import inked, rows_of
from _extract.linegeometry import baseline_of, share_a_baseline
from _extract.furnitureprintings import FurniturePrintings
from _extract.layertables import table_html
from _extract.runningheads import folioless_shape

NARROW_SHARE = 0.6
MIN_COLUMNS = 2
MIN_BODY_ROWS = 2
MAX_ROW_GAP_SHARE = 4.0
MAX_FOLIO_TOKENS = 1
BODY_KINDS = (TEXT_KIND, LIST_ITEM_KIND)
CAPTION_KINDS = (HEADING_KIND, FURNITURE_KINDS[0])
_IDENTIFIER_SUFFIX = "/parallel-columns"


@dataclass(frozen=True)
class _WorkShape:
    measure: float
    repeated_heads: frozenset[str]

    @classmethod
    def of(cls, blocks: DocumentBlocks) -> _WorkShape:
        widths = [block.bbox.width for page in blocks.pages for block in page.of_kind(TEXT_KIND)]
        repeated = FurniturePrintings(blocks.pages).repeated_shapes()
        return cls(statistics.median(widths) if widths else 0.0, repeated)

    def is_narrow(self, block: Block) -> bool:
        return block.bbox.width < NARROW_SHARE * self.measure

    def is_page_furniture(self, block: Block) -> bool:
        shape = folioless_shape(block.plain_text)
        if not shape:
            return block.is_furniture and len(block.plain_text.split()) <= MAX_FOLIO_TOKENS
        return block.is_furniture and shape in self.repeated_heads


class ParallelColumns:
    def __init__(self, work) -> None:
        self._work = work

    def refiled(self, blocks: DocumentBlocks) -> DocumentBlocks:
        shape = _WorkShape.of(blocks)
        return DocumentBlocks([_PageBands(self._work, page, shape).refiled() for page in blocks.pages])


class _PageBands:
    def __init__(self, work, page: PageBlocks, shape: _WorkShape) -> None:
        self._work = work
        self._page = page
        self._shape = shape
        self._wide = [block for block in page.of_kind(TEXT_KIND) if not shape.is_narrow(block)]

    def refiled(self) -> PageBlocks:
        blocks = list(self._page.blocks)
        for band in self._bands():
            if band.is_parallel(self._page.blocks):
                blocks = band.replaced_in(blocks, self._cells(band).rows())
        return PageBlocks(self._page.file_page, blocks)

    def _cells(self, band: _Band):
        if self._page.file_page in self._work.pixel_pages:
            return _EngineCells(band)
        return _LayerCells(band, self._work.layer, self._work.block_html)

    def _bands(self) -> list[_Band]:
        if not self._wide:
            return []
        grouped: dict[int, list[Block]] = {}
        for block in filter(self._may_stand_in_a_band, self._page.blocks):
            grouped.setdefault(self._gap_holding(block), []).append(block)
        return [_Band(self._page.file_page, members, self._work.layer).captioned() for members in grouped.values()
                if any(member.kind in BODY_KINDS for member in members)]

    def _may_stand_in_a_band(self, block: Block) -> bool:
        is_a_band_kind = block.kind in BODY_KINDS + CAPTION_KINDS and not self._shape.is_page_furniture(block)
        return is_a_band_kind and self._shape.is_narrow(block) and not self._lies_beside_wide_text(block)

    def _lies_beside_wide_text(self, block: Block) -> bool:
        middle = block.bbox.center[1]
        return any(wide.bbox.top <= middle <= wide.bbox.bottom for wide in self._wide)

    def _gap_holding(self, block: Block) -> int:
        return sum(1 for wide in self._wide if wide.bbox.bottom <= block.bbox.center[1])


class _Band:
    def __init__(self, file_page: int, blocks: list[Block], layer) -> None:
        self.file_page = file_page
        self.blocks = blocks
        self.box = Box.union([block.bbox for block in blocks])
        self.columns = _ColumnSpans(layer.chars_in(file_page, self.box), blocks).boxes(self.box)
        self._layer = layer

    def captioned(self) -> _Band:
        heading = [block for block in self.blocks if block.kind in BODY_KINDS or self._heads_its_column(block)]
        return self if len(heading) == len(self.blocks) else _Band(self.file_page, heading, self._layer)

    def _heads_its_column(self, block: Block) -> bool:
        bodies = self.members_of(self._column_of(block), BODY_KINDS)
        return bool(bodies) and block.bbox.center[1] < bodies[0].bbox.top

    def is_parallel(self, page_blocks: list[Block]) -> bool:
        bodies = [self.members_of(column, BODY_KINDS) for column in self.columns]
        if len(self.columns) < MIN_COLUMNS or not all(bodies):
            return False
        sets_text_columns = all(map(self._sets_a_text_column, self.columns))
        side_by_side = all(map(_stand_side_by_side, bodies, bodies[1:]))
        return sets_text_columns and side_by_side and not self._holds_other_content(page_blocks)

    def _sets_a_text_column(self, column: Box) -> bool:
        body_rows = self._rows_in(column, BODY_KINDS)
        return len(body_rows) >= MIN_BODY_ROWS and _run_on(self._rows_in(column, BODY_KINDS + CAPTION_KINDS))

    def _rows_in(self, column: Box, kinds: tuple[str, ...]) -> list[list]:
        boxes = [block.bbox for block in self.members_of(column, kinds)]
        return rows_of([char for box in boxes for char in self._layer.chars_in(self.file_page, box)])

    def members_of(self, column: Box, kinds: tuple[str, ...]) -> list[Block]:
        held = [block for block in self.blocks if block.kind in kinds and self._column_of(block) is column]
        return sorted(held, key=lambda block: block.bbox.top)

    def _column_of(self, block: Block) -> Box:
        return max(self.columns, key=lambda column: _width_shared(column, block.bbox))

    def _holds_other_content(self, page_blocks: list[Block]) -> bool:
        return any(not block.is_furniture and block not in self.blocks and self.box.contains(block.bbox.center)
                   for block in page_blocks)

    def replaced_in(self, blocks: list[Block], rows: list[list[str]]) -> list[Block]:
        first = next(block for block in blocks if block in self.blocks)
        table = Block(self.file_page, TABLE_KIND, table_html(rows), self.box, {},
                      first.identifier + _IDENTIFIER_SUFFIX)
        return [table if block is first else block for block in blocks if block is first or block not in self.blocks]


def _run_on(rows: list[list]) -> bool:
    baselines = sorted(baseline_of(row) for row in rows)
    size = statistics.median(char.size for row in rows for char in inked(row)) if rows else 0.0
    return all(lower - upper <= MAX_ROW_GAP_SHARE * size for upper, lower in zip(baselines, baselines[1:]))


def _width_shared(first: Box, second: Box) -> float:
    return min(first.right, second.right) - max(first.left, second.left)


def _stand_side_by_side(left: list[Block], right: list[Block]) -> bool:
    return Box.union([block.bbox for block in left]).spans_rows(*_vertical_extent(right))


def _vertical_extent(blocks: list[Block]) -> tuple[float, float]:
    box = Box.union([block.bbox for block in blocks])
    return box.top, box.bottom


class _ColumnSpans:
    def __init__(self, chars: list, blocks: list[Block]) -> None:
        inked_boxes = [char.bbox for char in chars if not char.is_blank]
        self._spans = sorted((box.left, box.right) for box in inked_boxes or [block.bbox for block in blocks])

    def boxes(self, band: Box) -> list[Box]:
        return [Box(left, band.top, right, band.bottom) for left, right in self._merged()]

    def _merged(self) -> list[tuple[float, float]]:
        merged: list[tuple[float, float]] = []
        for left, right in self._spans:
            if merged and left - merged[-1][1] < MIN_GUTTER_POINTS:
                merged[-1] = (merged[-1][0], max(merged[-1][1], right))
            else:
                merged.append((left, right))
        return merged


class _EngineCells:
    def __init__(self, band: _Band) -> None:
        self._band = band

    def rows(self) -> list[list[str]]:
        captions = [[block.html for block in self._band.members_of(column, CAPTION_KINDS)]
                    for column in self._band.columns]
        bodies = [" ".join(block.html for block in self._band.members_of(column, BODY_KINDS))
                  for column in self._band.columns]
        return _captioned(captions, bodies)


class _LayerCells:
    def __init__(self, band: _Band, layer, block_html) -> None:
        self._band = band
        self._block_html = block_html
        self._rows = [rows_of(layer.chars_in(band.file_page, column)) for column in band.columns]

    def rows(self) -> list[list[str]]:
        if _pair_by_baseline(self._rows):
            return [[self._block_html.of([row]) for row in paired] for paired in zip(*self._rows)]
        captions = [[self._block_html.of([row]) for row in rows if self._is_a_caption(row)] for rows in self._rows]
        bodies = [self._block_html.of([row for row in rows if not self._is_a_caption(row)]) for rows in self._rows]
        return _captioned(captions, bodies)

    def _is_a_caption(self, row: list) -> bool:
        middle = _middle_of(row)
        return any(block.kind in CAPTION_KINDS and block.bbox.contains(middle) for block in self._band.blocks)


def _pair_by_baseline(columns: list[list[list]]) -> bool:
    if len({len(rows) for rows in columns}) != 1:
        return False
    return all(share_a_baseline(paired) for paired in zip(*columns))


def _middle_of(row: list) -> tuple[float, float]:
    return Box.union([char.bbox for char in inked(row)]).center


def _captioned(captions: list[list[str]], bodies: list[str]) -> list[list[str]]:
    return [list(row) for row in zip_longest(*captions, fillvalue="")] + [bodies]
