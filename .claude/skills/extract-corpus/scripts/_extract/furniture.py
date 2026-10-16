from __future__ import annotations

import dataclasses
import html
import re
import statistics

import pagetext

from _extract.blocks import FOOTNOTE_KIND, FURNITURE_KINDS, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.box import Box
from _extract.furnitureprintings import FurniturePrintings
from _extract.headings import MIN_SHAPE_CHARS, SmallCapitalFont, reads_as_body_text
from _extract.layerlines import STYLE_SIZE_TOLERANCE_POINTS, row_text, rows_of
from _extract.lists import RIGHT_EDGE_TOLERANCE_POINTS
from _extract.runningheads import FurnitureProfile, folioless_shape

HEADER_KIND = FURNITURE_KINDS[0]
MIN_SPLIT_ROWS = 2
NEXT_LINE_PITCHES = 1.5
MIN_STATEMENT_SIZE_SHARE = 0.85
_HEAD_SUFFIX = "/running-head"
_LINE_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


class WorkFurniture:
    def __init__(self, layer) -> None:
        self._layer = layer

    def refiled(self, blocks: DocumentBlocks) -> DocumentBlocks:
        printed = _PrintedFurniture(self._layer, blocks.pages)
        return DocumentBlocks([_PageFurniture(self._layer, page, printed).refiled() for page in blocks.pages])

    def profile(self, blocks: DocumentBlocks) -> FurnitureProfile:
        return FurnitureProfile(_furniture_type_sizes(self._layer, blocks.pages))


class _PrintedFurniture:
    def __init__(self, layer, pages: list[PageBlocks]) -> None:
        self.printings = FurniturePrintings(pages)
        self.profile = FurnitureProfile(_furniture_type_sizes(layer, pages))


def _furniture_type_sizes(layer, pages: list[PageBlocks]) -> dict[str, float]:
    sizes: dict[str, list[float]] = {}
    for page in pages:
        for block in (block for block in page.blocks if block.is_furniture):
            chars = layer.chars_in(page.file_page, block.bbox)
            sizes.setdefault(folioless_shape(block.plain_text), []).extend(_sizes_of(chars))
    return {shape: statistics.median(found) for shape, found in sizes.items() if found}


class _PageFurniture:
    def __init__(self, layer, page: PageBlocks, printed: _PrintedFurniture) -> None:
        self._layer = layer
        self._page = page
        self._printed = printed
        self._printings = printed.printings

    def refiled(self) -> PageBlocks:
        kept = [self._refiled_block(block) for block in self._page.blocks if not self._is_a_line_of_the_text(block)]
        top = min((block for block in kept if self._is_text(block)), key=lambda block: block.bbox.top, default=None)
        split = [piece for block in kept for piece in (self._split(block) if block is top else [block])]
        return PageBlocks(self._page.file_page, split)

    def _refiled_block(self, block: Block) -> Block:
        if self._is_a_heading_of_the_text(block):
            return self._as_heading(block)
        if self._sets_a_statement_of_the_text(block) or self._sets_a_line_beneath_the_text(block):
            return self._as_paragraph(block)
        return block

    def _sets_a_line_beneath_the_text(self, block: Block) -> bool:
        is_a_folio = pagetext.BARE_FOLIO_RE.match(block.plain_text) is not None
        if not block.is_furniture or self._printings.repeats(block.plain_text) or is_a_folio:
            return False
        return _LineBeneathTheText(self._layer, self._page).holds(block)

    def _sets_a_statement_of_the_text(self, block: Block) -> bool:
        statements = [other for other in self._page.blocks if self._reads_as_a_sentence_once_printed(other)]
        return self._is_printed_once_at_the_head(block) and any(_shares_a_row(block, other) for other in statements)

    def _reads_as_a_sentence_once_printed(self, block: Block) -> bool:
        reads_as_a_sentence = reads_as_body_text(block.plain_text) and self._sets_near_the_text_size(block)
        return self._is_printed_once_at_the_head(block) and reads_as_a_sentence and self._runs_into_text(block)

    def _runs_into_text(self, block: Block) -> bool:
        below = [other for other in self._page.content if other.bbox.top >= block.bbox.center[1]]
        following = min(below, key=lambda other: other.bbox.top, default=None)
        return following is not None and following.kind == TEXT_KIND

    def _sets_near_the_text_size(self, block: Block) -> bool:
        sizes = self._sizes_in([block])
        text_sizes = self._sizes_in([other for other in self._page.blocks if other.kind == TEXT_KIND])
        if not (sizes and text_sizes):
            return False
        return statistics.median(sizes) >= MIN_STATEMENT_SIZE_SHARE * statistics.median(text_sizes)

    def _sizes_in(self, blocks: list[Block]) -> list[float]:
        return [size for block in blocks for size in _sizes_of(self._layer.chars_in(self._page.file_page, block.bbox))]

    def _is_printed_once_at_the_head(self, block: Block) -> bool:
        return block.kind == HEADER_KIND and self._printings.prints_once(block.plain_text)

    def _is_a_line_of_the_text(self, block: Block) -> bool:
        if not (block.is_furniture and self._printings.prints_once(block.plain_text)):
            return False
        return any(other.kind == TEXT_KIND and other.bbox.contains(block.bbox.center) for other in self._page.blocks)

    def _is_a_heading_of_the_text(self, block: Block) -> bool:
        if not block.is_furniture:
            return False
        return self._page.stands_between_body_blocks(block) or self._opens_its_running_heads_in_display_type(block) \
            or self._sets_a_divider_between_the_running_head_and_the_text(block)

    def _sets_a_divider_between_the_running_head_and_the_text(self, block: Block) -> bool:
        if not self._printings.prints_once(block.plain_text):
            return False
        if not SmallCapitalFont(self._layer.chars_in(self._page.file_page, block.bbox)).sets():
            return False
        head_above = any(self._is_a_running_head_above(other, block) for other in self._page.blocks)
        return head_above and any(self._is_text(other) and other.bbox.top >= block.bbox.bottom
                                  for other in self._page.blocks)

    def _is_a_running_head_above(self, other: Block, block: Block) -> bool:
        repeated = self._printings.repeats(other.plain_text)
        return other is not block and other.is_furniture and repeated and other.bbox.bottom <= block.bbox.top

    def _opens_its_running_heads_in_display_type(self, block: Block) -> bool:
        shape = folioless_shape(block.plain_text)
        sizes = _sizes_of(self._layer.chars_in(self._page.file_page, block.bbox))
        if not (shape and sizes) or self._printings.first_page_printing(shape) != self._page.file_page:
            return False
        return self._printed.profile.sets_in_display_type(shape, statistics.median(sizes))

    @staticmethod
    def _as_paragraph(block: Block) -> Block:
        return dataclasses.replace(block, kind=TEXT_KIND, html=f"<p>{_LINE_BREAK_RE.sub(' ', block.html)}</p>")

    @staticmethod
    def _as_heading(block: Block) -> Block:
        return dataclasses.replace(block, kind=HEADING_KIND)

    def _split(self, block: Block) -> list[Block]:
        rows = rows_of(self._layer.chars_in(self._page.file_page, block.bbox))
        if len(rows) < MIN_SPLIT_ROWS or not self._is_running_head(rows[0]):
            return [block]
        head_box = _box_of(rows[0])
        head = Block(block.file_page, HEADER_KIND, html.escape(row_text(rows[0]), quote=False), head_box, {},
                     block.identifier + _HEAD_SUFFIX)
        body_box = Box(block.bbox.left, head_box.bottom, block.bbox.right, block.bbox.bottom)
        return [head, dataclasses.replace(block, bbox=body_box)]

    def _is_running_head(self, row: list) -> bool:
        text = row_text(row)
        shape = folioless_shape(text)
        if len(shape) < MIN_SHAPE_CHARS or self._printings.pages_printing(shape) == 0:
            return False
        return not self._printed.profile.sets_larger(text, statistics.median(_sizes_of(row)))

    @staticmethod
    def _is_text(block: Block) -> bool:
        return not block.is_furniture and block.kind != FOOTNOTE_KIND


class _LineBeneathTheText:
    def __init__(self, layer, page: PageBlocks) -> None:
        self._layer = layer
        self._page = page

    def holds(self, block: Block) -> bool:
        above = self._text_block_above(block)
        if above is None:
            return False
        text_rows, own_rows = self._rows(above), self._rows(block)
        if len(text_rows) < MIN_SPLIT_ROWS or len(own_rows) != 1:
            return False
        row = own_rows[0]
        return _sits_on_the_next_line(text_rows, row) and _sets_in_one_size(text_rows, row) \
            and _aligns_right_under(text_rows, row)

    def _text_block_above(self, block: Block) -> Block | None:
        middle_x, middle_y = block.bbox.center
        above = [other for other in self._page.blocks if other.kind == TEXT_KIND and other.bbox.bottom <= middle_y
                 and other.bbox.left <= middle_x <= other.bbox.right]
        return max(above, key=lambda other: other.bbox.bottom, default=None)

    def _rows(self, block: Block) -> list[list]:
        return rows_of([char for char in self._layer.chars_in(self._page.file_page, block.bbox) if not char.is_blank])


def _sits_on_the_next_line(text_rows: list[list], row: list) -> bool:
    centers = [_box_of(each).center[1] for each in text_rows]
    pitch = statistics.median(later - earlier for earlier, later in zip(centers, centers[1:]))
    return 0 < _box_of(row).center[1] - centers[-1] <= NEXT_LINE_PITCHES * pitch


def _aligns_right_under(text_rows: list[list], row: list) -> bool:
    text_box = Box.union([_box_of(each) for each in text_rows])
    own_box = _box_of(row)
    ends_at_the_right_edge = abs(own_box.right - text_box.right) <= RIGHT_EDGE_TOLERANCE_POINTS
    return ends_at_the_right_edge and own_box.left > text_box.center[0]


def _sets_in_one_size(text_rows: list[list], row: list) -> bool:
    text_size = statistics.median(char.size for each in text_rows for char in each)
    return abs(statistics.median(char.size for char in row) - text_size) <= STYLE_SIZE_TOLERANCE_POINTS


def _shares_a_row(block: Block, other: Block) -> bool:
    middle = block.bbox.center[1]
    return other.bbox.spans_rows(middle, middle)


def _box_of(row: list) -> Box:
    return Box.union([char.bbox for char in row])


def _sizes_of(chars: list) -> list[float]:
    return [char.size for char in chars if not char.is_blank]
