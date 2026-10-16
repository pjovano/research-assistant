from __future__ import annotations

from _extract.arrowstacks import ArrowStack
from _extract.blocks import EQUATION_KIND, FOOTNOTE_KIND, TABLE_KIND, Block, PageBlocks
from _extract.enginemath import EngineNotation
from _extract.fusedmarks import FusedMarks
from _extract.guardedmath import GuardedMath, LayerFormulas, NotationLog
from _extract.layerlines import PageLines
from _extract.markguard import MarkGuard
from _extract.proseguard import NumeralGuard, ProseGuard

_TABLE_TAG = "<table"


class BlockReading:
    def __init__(self, work) -> None:
        self._layer = work.layer
        self._block_html = work.block_html
        self._pixel_pages = work.pixel_pages
        self._engine_notation = EngineNotation()
        self._notation_log = NotationLog()
        self._guarded_math = GuardedMath(self._notation_log)
        self._prose_guard = ProseGuard()
        self._numeral_guard = NumeralGuard()
        self._lines: PageLines | None = None
        self._unstacked_lines: PageLines | None = None
        self._page = PageBlocks(0, [])
        self._fused_marks = FusedMarks(set())
        self._reads_pixels = False

    def read_page(self, page: PageBlocks) -> None:
        self._reads_pixels = page.file_page in self._pixel_pages
        self._page = page
        self._fused_marks = FusedMarks.of_page(page)
        self._lines = PageLines(self._layer, page.file_page, page.blocks)
        self._unstacked_lines = None

    @property
    def lines(self) -> PageLines:
        return self._lines

    @property
    def reads_pixels(self) -> bool:
        return self._reads_pixels

    def trusts_the_layer(self, file_page: int) -> bool:
        return not self._reads_pixels or self._layer.is_drawn(file_page)

    def notation_log(self) -> list[str]:
        return self._notation_log.entries()

    def body_html(self, block: Block) -> str:
        if block.kind == FOOTNOTE_KIND:
            return ""
        return self.html_of(block)

    def html_of(self, block: Block) -> str:
        if self.is_table(block) or self._lines is None:
            return self._engine_notation.replaced(block.html)
        if self._reads_pixels:
            return self._engine_notation.replaced(self._guarded_html(block))
        return self.built_html(block) or self._unbuilt_html(block)

    def _unbuilt_html(self, block: Block) -> str:
        if self._stacked_into_fractions(block):
            return ""
        return self._engine_notation.replaced(block.html)

    def _stacked_into_fractions(self, block: Block) -> bool:
        drawn = _inked(self._layer.unstacked().chars_in(block.file_page, block.bbox))
        kept = set(_inked(self._layer.chars_in(block.file_page, block.bbox)))
        return bool(drawn) and kept.isdisjoint(drawn)

    def html_of_rows(self, rows: list[list]) -> str:
        return self._block_html.of(rows)

    def built_html(self, block: Block) -> str:
        return self._html_of_rows(block, self._lines.of(block))

    def _html_of_rows(self, block: Block, rows: list[list]) -> str:
        return self._block_html.stacked(rows) if block.kind == EQUATION_KIND else self._block_html.of(rows)

    def _unstacked_html(self, block: Block) -> str:
        return self._html_of_rows(block, self._unstacked_rows(block))

    def _unstacked_rows(self, block: Block) -> list[list]:
        if self._unstacked_lines is None:
            self._unstacked_lines = PageLines(self._layer.unstacked(), self._page.file_page, self._page.blocks)
        return self._unstacked_lines.of(block)

    @staticmethod
    def is_table(block: Block) -> bool:
        return block.kind == TABLE_KIND or _TABLE_TAG in block.html

    def _guarded_html(self, block: Block) -> str:
        layer = self._layer_formulas(block)
        if self._layer.is_drawn(block.file_page):
            engine_html = self._layer_checked(block, layer.html)
        else:
            engine_html = self._fused_marks.corrected(self._numeral_guard.corrected(block.html, layer.html), layer.html)
        return self._guarded_math.checked_against(block.file_page, engine_html, layer)

    def _layer_checked(self, block: Block, layer_html: str) -> str:
        return MarkGuard(layer_html).corrected(self._prose_guard.corrected(block.html, layer_html))

    def _layer_formulas(self, block: Block) -> LayerFormulas:
        arrow_stack = ArrowStack(self._unstacked_rows(block)).latex() if block.kind == EQUATION_KIND else None
        return LayerFormulas(self._unstacked_html(block), arrow_stack, self._layer.is_drawn(block.file_page))


def _inked(chars: list) -> list:
    return [char for char in chars if not char.is_blank]
