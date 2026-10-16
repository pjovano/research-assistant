from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

import pagetext

FIRST_FILE_PAGE = 1


@dataclass(frozen=True)
class VolumeDocument:
    pdf: Path
    page_count: int
    outline: tuple[tuple[int, str, int], ...]

    @classmethod
    def read(cls, pdf: Path) -> VolumeDocument:
        with pymupdf.open(pdf) as document:
            page_count = document.page_count
        outline = tuple(row for row in pagetext.outline_entries(pdf) if row[2] >= FIRST_FILE_PAGE)
        return cls(pdf, page_count, outline)

    @property
    def basename(self) -> str:
        return self.pdf.stem

    def has_outline(self) -> bool:
        return bool(self.outline)

    def rows_at_or_above(self, level: int | None) -> OutlineRows:
        kept = [row for row in self.outline if level is None or row[0] <= level]
        return OutlineRows(kept, self.page_count)


class OutlineRows:
    def __init__(self, rows: list[tuple[int, str, int]], page_count: int) -> None:
        self._rows = rows
        self._page_count = page_count

    def __len__(self) -> int:
        return len(self._rows)

    def row(self, index: int) -> tuple[int, str, int]:
        return self._rows[index]

    def last_page_of(self, index: int) -> int:
        level, _, first_page = self._rows[index]
        later_openings = (page for lvl, _, page in self._rows[index + 1:] if lvl <= level)
        return max(next(later_openings, self._page_count + 1) - 1, first_page)
