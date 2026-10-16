from __future__ import annotations

from pathlib import Path

import pymupdf

import vault


class PageCounts:
    def __init__(self, directories: tuple[Path, ...]) -> None:
        self._directories = directories

    def of(self, pdf: str) -> int | None:
        located = vault.locate_pdf(pdf, self._directories)
        return None if located is None else self._counted(located)

    @staticmethod
    def _counted(path: Path) -> int | None:
        try:
            with pymupdf.open(path) as document:
                return document.page_count
        except (RuntimeError, OSError):
            return None
