from __future__ import annotations

from pathlib import Path

import pymupdf
import pagetext

from .constants import RENDER_DPI

FIRST_PAGE = 1


def widened(rect: pymupdf.Rect, horizontal: float, vertical: float) -> pymupdf.Rect:
    return pymupdf.Rect(rect.x0 - horizontal, rect.y0 - vertical, rect.x1 + horizontal, rect.y1 + vertical)


class FilePage:
    def __init__(self, number: int, page_count: int, file_name: str) -> None:
        self._number = number
        self._page_count = page_count
        self._file_name = file_name

    def require_in_range(self) -> None:
        if FIRST_PAGE <= self._number <= self._page_count:
            return
        raise SystemExit(
            f"{self._file_name} has pages {FIRST_PAGE}..{self._page_count}; asked for "
            f"{self._number}. Page numbers are 1-based, as they are for render --page, "
            "toc scan, and outline entries.")


class PageRender:
    def __init__(self, pdf_path: Path, dpi: int = RENDER_DPI) -> None:
        self._path = pdf_path
        self._dpi = dpi

    def save(self, page_number: int = FIRST_PAGE) -> Path:
        with pymupdf.open(self._path) as doc:
            FilePage(page_number, doc.page_count, self._path.name).require_in_range()
        return pagetext.render_pages(self._path, [page_number], dpi=self._dpi)[0]
