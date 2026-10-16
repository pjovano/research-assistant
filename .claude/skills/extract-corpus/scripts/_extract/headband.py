from __future__ import annotations

import statistics
from dataclasses import dataclass

from _extract.blocks import BODY_KINDS, FURNITURE_KINDS, HEADING_KIND, Block, DocumentBlocks, PageBlocks
from _extract.box import Box
from _extract.edgelines import MOST_PAGES_SHARE
from _extract.runningheads import DISPLAY_TYPE_RATIO, REPEATED_PAGES, folioless_shape

HEAD_KINDS = FURNITURE_KINDS + (HEADING_KIND,)


@dataclass(frozen=True)
class RunningHeadBand:
    top: float
    bottom: float
    type_size: float

    @classmethod
    def of(cls, blocks: DocumentBlocks, layer) -> RunningHeadBand | None:
        heads = RepeatedTopLines(blocks.pages).printings()
        sizes = [char.size for head in heads for char in layer.chars_in(head.file_page, head.bbox) if not char.is_blank]
        if not sizes:
            return None
        return cls(min(head.bbox.top for head in heads), max(head.bbox.bottom for head in heads),
                   statistics.median(sizes))

    def holds(self, box: Box | None, size: float | None) -> bool:
        if box is None or size is None:
            return False
        middle = box.center[1]
        return self.top <= middle <= self.bottom and size < self.type_size * DISPLAY_TYPE_RATIO


class RepeatedTopLines:
    def __init__(self, pages: list[PageBlocks]) -> None:
        self._page_count = len(pages)
        self._by_wording: dict[str, list[Block]] = {}
        for block in (block for page in pages for block in _top_lines(page)):
            self._by_wording.setdefault(folioless_shape(block.plain_text), []).append(block)
        self._by_wording.pop("", None)

    def printings(self) -> list[Block]:
        repeated = [block for printings in self._by_wording.values() if _pages_of(printings) >= REPEATED_PAGES
                    for block in printings]
        kept = _at_their_usual_height(repeated)
        return kept if _pages_of(kept) > self._page_count * MOST_PAGES_SHARE else []


def _at_their_usual_height(printings: list[Block]) -> list[Block]:
    if not printings:
        return []
    by_height = sorted(printings, key=lambda block: block.bbox.center[1])
    usual = by_height[len(by_height) // 2].bbox
    return [block for block in printings if usual.top <= block.bbox.center[1] <= usual.bottom]


def _pages_of(printings: list[Block]) -> int:
    return len({block.file_page for block in printings})


def _top_lines(page: PageBlocks) -> list[Block]:
    body_top = min((block.bbox.top for block in page.blocks if block.kind in BODY_KINDS), default=None)
    if body_top is None:
        return []
    return [block for block in page.blocks
            if block.kind in HEAD_KINDS and block.bbox.bottom <= body_top and _opens_its_column(page, block)]


def _opens_its_column(page: PageBlocks, block: Block) -> bool:
    return not any(other.bbox.bottom <= block.bbox.top and other.bbox.shares_a_column_with(block.bbox)
                   for other in page.blocks)
