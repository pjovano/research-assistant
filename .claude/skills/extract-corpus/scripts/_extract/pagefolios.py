from __future__ import annotations

import statistics

from _pagetext.folio import FolioResolver, FolioSignals, PageInput

from _extract.blocks import PageBlocks
from _extract.layerhtml import RAISED_OFFSET_SHARE
from _extract.layerlines import inked

FURNITURE_LINE_SEPARATOR = "\n"


class FolioReader:
    def __init__(self, layer) -> None:
        self._layer = layer

    def of(self, pages: list[PageBlocks]) -> dict[int, str | None]:
        return {file_page: signals.folio for file_page, signals in self.signals(pages).items()}

    def signals(self, pages: list[PageBlocks]) -> dict[int, FolioSignals]:
        inputs = [self._input(page) for page in pages]
        return dict(zip((page.file_page for page in pages), FolioResolver().signals(inputs)))

    def _input(self, page: PageBlocks) -> PageInput:
        return PageInput(self._furniture_text(page), self._layer.label(page.file_page), self._edge_text(page.file_page))

    @staticmethod
    def _furniture_text(page: PageBlocks) -> str:
        return FURNITURE_LINE_SEPARATOR.join(block.plain_text for block in page.blocks if block.is_furniture)

    def _edge_text(self, file_page: int) -> str:
        texts = [self._baseline_text(file_page, line) for line in self._layer.lines(file_page)]
        return FURNITURE_LINE_SEPARATOR.join(text for text in texts if text.strip())

    def _baseline_text(self, file_page: int, line) -> str:
        return _BaselineText(self._layer.chars_in(file_page, line.box)).text()


class _BaselineText:
    def __init__(self, chars: list) -> None:
        drawn = inked(chars)
        self._chars = chars
        self._size = statistics.median(char.size for char in drawn) if drawn else 0.0
        self._baseline = statistics.median(char.baseline for char in drawn) if drawn else 0.0

    def text(self) -> str:
        return "".join(char.char for char in self._chars if not self._raises(char))

    def _raises(self, char) -> bool:
        is_smaller = char.size < self._size
        return is_smaller and self._baseline - char.baseline > RAISED_OFFSET_SHARE * self._size


def folio_log(signals: dict[int, FolioSignals]) -> list[str]:
    return [f"file p. {file_page}: {finding}" for file_page, page_signals in signals.items()
            for finding in page_signals.disagreements()]
