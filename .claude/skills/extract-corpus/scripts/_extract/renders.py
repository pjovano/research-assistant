from __future__ import annotations

from pathlib import Path

import pagetext

TEXT_LAYER_JUDGING_DPI = 120


class PageRenders:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def by_page(self, pages: list[int]) -> dict[int, str]:
        return {page: str(render) for page in pages for render in pagetext.render_pages(self._pdf_path, [page])}


class JudgingRenders:
    def __init__(self, pdf_path: Path, layer, pixel_pages: frozenset[int] = frozenset()) -> None:
        self._pdf_path = pdf_path
        self._layer = layer
        self._pixel_pages = pixel_pages

    def by_page(self, pages: list[int]) -> dict[int, str]:
        return {page: str(render) for page in pages
                for render in pagetext.render_pages(self._pdf_path, [page], dpi=self._dpi_of(page))}

    def _dpi_of(self, file_page: int) -> int:
        return TEXT_LAYER_JUDGING_DPI if self._is_read_from_its_text_layer(file_page) else pagetext.DEFAULT_RENDER_DPI

    def _is_read_from_its_text_layer(self, file_page: int) -> bool:
        drawn = self._layer.has_text(file_page) and self._layer.is_drawn(file_page)
        return drawn and file_page not in self._pixel_pages
