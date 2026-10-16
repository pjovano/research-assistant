from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .constants import (
    GUTTED_PAGE_MIN_CHARS,
    GUTTED_PAGE_RATIO,
    MIN_SOURCE_TEXT_CHARS,
    TOTAL_TEXT_RATIO,
    VERIFY_SAMPLE_PAGES,
)
from .sampling import spread_positions


class SampledPages:
    def __init__(self, page_count: int, limit: int = VERIFY_SAMPLE_PAGES) -> None:
        self._page_count = page_count
        self._limit = limit

    def indices(self) -> list[int]:
        return spread_positions(self._page_count, self._limit)


@dataclass(frozen=True)
class _TextSample:
    indices: list[int]
    before: list[int]
    after: list[int]

    def total_before(self) -> int:
        return sum(self.before)

    def total_after(self) -> int:
        return sum(self.after)

    def gutted_pages(self) -> list[int]:
        return [
            self.indices[n]
            for n, chars in enumerate(self.before)
            if chars >= GUTTED_PAGE_MIN_CHARS and self.after[n] < chars * GUTTED_PAGE_RATIO
        ]


class GuttingCheck:
    def __init__(self, src_path: Path, dest: Path) -> None:
        self._src = src_path
        self._dest = dest

    def run(self) -> None:
        src_pages, dest_pages = self._page_counts()
        self._check_no_pages_lost(src_pages, dest_pages)
        indices = SampledPages(src_pages).indices()
        before = self._text_lengths(self._src, indices)
        if sum(before) < MIN_SOURCE_TEXT_CHARS:
            return
        sample = _TextSample(indices, before, self._text_lengths(self._dest, indices))
        if dest_pages == src_pages:
            self._check_no_page_gutted(sample)
        self._check_total_text_retained(sample)

    def _page_counts(self) -> tuple[int, int]:
        with pymupdf.open(self._src) as src_doc, pymupdf.open(self._dest) as dest_doc:
            return src_doc.page_count, dest_doc.page_count

    def _check_no_pages_lost(self, src_pages: int, dest_pages: int) -> None:
        if dest_pages < src_pages:
            self._reject(
                f"{src_pages - dest_pages} of {src_pages} pages did not survive writing.")

    def _text_lengths(self, path: Path, indices: list[int]) -> list[int]:
        with pymupdf.open(path) as doc:
            return [len(doc[i].get_text().strip()) for i in indices]

    def _check_no_page_gutted(self, sample: _TextSample) -> None:
        gutted = sample.gutted_pages()
        if gutted:
            self._reject(
                f"{len(gutted)} sampled page(s) lost their text, starting at page "
                f"{gutted[0]}. The source is damaged in a way this path cannot repair.")

    def _check_total_text_retained(self, sample: _TextSample) -> None:
        if sample.total_after() < sample.total_before() * TOTAL_TEXT_RATIO:
            self._reject(
                f"text collapsed from {sample.total_before()} to {sample.total_after()} "
                "characters. The source is damaged in a way this path cannot repair.")

    def _reject(self, reason: str) -> None:
        raise SystemExit(f"Refusing to keep {self._dest.name}: {reason}")
