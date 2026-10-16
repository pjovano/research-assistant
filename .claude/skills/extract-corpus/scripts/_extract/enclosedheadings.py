from __future__ import annotations

from _extract.blocks import HEADING_KIND, TEXT_KIND, Block
from _extract.layerlines import PageLines, box_of, box_of_rows

_PIECE_SUFFIX = "/piece-"


class EnclosedHeadings:
    def __init__(self, lines: PageLines) -> None:
        self._lines = lines

    def split(self, blocks: list[Block]) -> list[Block]:
        split = self._split_blocks(blocks)
        lifted = {id(piece) for pieces in split.values() for piece in pieces if piece.kind == HEADING_KIND}
        return [piece for block in blocks if id(block) not in lifted for piece in split.get(id(block), [block])]

    def _split_blocks(self, blocks: list[Block]) -> dict[int, list[Block]]:
        split: dict[int, list[Block]] = {}
        for block, headings in self._enclosing(blocks):
            pieces = _EnclosingBlock(block, self._lines.columns_of(block), headings).read()
            if pieces:
                split[id(block)] = pieces
        return split

    @staticmethod
    def _enclosing(blocks: list[Block]) -> list[tuple[Block, list[Block]]]:
        texts = [block for block in blocks if block.kind == TEXT_KIND]
        enclosed: dict[int, list[Block]] = {}
        for heading in (block for block in blocks if block.kind == HEADING_KIND):
            around = [text for text in texts if text.bbox.contains(heading.bbox.center)]
            if around:
                enclosed.setdefault(id(min(around, key=_area)), []).append(heading)
        return [(text, enclosed[id(text)]) for text in texts if id(text) in enclosed]


class _EnclosingBlock:
    def __init__(self, block: Block, columns: list[list[list]], headings: list[Block]) -> None:
        self._block = block
        self._columns = [column for column in columns if column]
        self._headings = headings

    def read(self) -> list[Block]:
        sequence = [item for index, column in enumerate(self._columns)
                    for item in _grouped(self._in_reading_order(column, self._headings_of(index)))]
        if not _a_heading_precedes_text(sequence):
            return []
        return [item if isinstance(item, Block) else self._piece(sequence, index)
                for index, item in enumerate(sequence)]

    def _headings_of(self, column_index: int) -> list[Block]:
        return [heading for heading in self._headings if self._column_of(heading) == column_index]

    def _column_of(self, heading: Block) -> int | None:
        return next((index for index, column in enumerate(self._columns) if _lies_across(heading, column)), None)

    @staticmethod
    def _in_reading_order(column: list[list], headings: list[Block]) -> list:
        placed = [(box_of(source).center[1], source) for source in column]
        placed += [(heading.bbox.center[1], heading) for heading in headings]
        return [item for _middle, item in sorted(placed, key=lambda pair: pair[0])]

    def _piece(self, sequence: list, index: int) -> Block:
        following = sequence[index + 1] if index + 1 < len(sequence) else None
        continued = self._block.continues if following is None else not isinstance(following, Block)
        return Block(self._block.file_page, self._block.kind, "", box_of_rows(sequence[index]), {},
                     f"{self._block.identifier}{_PIECE_SUFFIX}{index}", continued)


def _lies_across(heading: Block, column: list[list]) -> bool:
    column_box = box_of_rows(column)
    return column_box.left <= heading.bbox.center[0] <= column_box.right


def _grouped(items: list) -> list:
    grouped: list = []
    for item in items:
        if isinstance(item, Block):
            grouped.append(item)
        elif grouped and not isinstance(grouped[-1], Block):
            grouped[-1].append(item)
        else:
            grouped.append([item])
    return grouped


def _a_heading_precedes_text(sequence: list) -> bool:
    first_heading = next((index for index, item in enumerate(sequence) if isinstance(item, Block)), None)
    return first_heading is not None and any(not isinstance(item, Block) for item in sequence[first_heading + 1:])


def _area(block: Block) -> float:
    return block.bbox.width * (block.bbox.bottom - block.bbox.top)
