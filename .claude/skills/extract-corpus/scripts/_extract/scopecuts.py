from __future__ import annotations

import bisect

from _extract.blocks import TEXT_KIND, Block
from _extract.layerlines import PageLines, box_of, box_of_rows
from _extract.spans import ScopeCut

_PIECE_SUFFIX = "/scope-piece-"


class ScopeCuts:
    def __init__(self, lines: PageLines, cuts: list[ScopeCut]) -> None:
        self._lines = lines
        self._cuts = cuts

    def split(self, blocks: list[Block]) -> list[Block]:
        return [piece for block in blocks for piece in self._pieces(block)]

    def _pieces(self, block: Block) -> list[Block]:
        if block.kind != TEXT_KIND:
            return [block]
        stretches = _stretches(self._lines.of(block), self._positions_reaching(block))
        if len(stretches) < 2:
            return [block]
        last = len(stretches) - 1
        return [_piece(block, index, rows, block.continues and index == last)
                for index, rows in enumerate(stretches)]

    def _positions_reaching(self, block: Block) -> list[float]:
        return sorted(cut.position for cut in self._cuts if cut.reaches(block.bbox))


def _stretches(rows: list[list], positions: list[float]) -> list[list[list]]:
    stretches: dict[int, list[list]] = {}
    for row in rows:
        stretches.setdefault(bisect.bisect_right(positions, box_of(row).center[1]), []).append(row)
    return [stretches[stretch] for stretch in sorted(stretches)]


def is_a_scope_piece(block: Block) -> bool:
    return _PIECE_SUFFIX in block.identifier


def _piece(block: Block, index: int, rows: list[list], continued: bool) -> Block:
    identifier = f"{block.identifier}{_PIECE_SUFFIX}{index}"
    return Block(block.file_page, block.kind, "", box_of_rows(rows), {}, identifier, continued)
