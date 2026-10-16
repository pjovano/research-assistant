from __future__ import annotations

from _extract.console import FORCE_OCR_FLAG
from _extract.ranges import PageRanges
from _extract.request import FORCE_OCR_PAGES_FLAG

CHAPTER_LEVEL = 1
FIRST_PAGE = 1


class PixelChapters:
    def __init__(self, headings: list[dict], page_count: int) -> None:
        self._starts = sorted({heading["file_page"] for heading in headings if heading["level"] == CHAPTER_LEVEL})
        self._page_count = page_count

    def flags_covering(self, flags: list[str], file_pages: list[int]) -> list[str]:
        if FORCE_OCR_FLAG in flags:
            return list(flags)
        forced = self.forced_pages(flags) | self._chapters_holding(file_pages)
        return [*self._without_forced_pages(flags), FORCE_OCR_PAGES_FLAG, PageRanges().compact(sorted(forced))]

    def chapters(self) -> list[range]:
        starts = sorted({FIRST_PAGE, *(start for start in self._starts if start <= self._page_count)})
        return [self._chapter_of(start) for start in starts]

    def widens(self, flags: list[str], file_pages: list[int]) -> bool:
        unforced = self._chapters_holding(file_pages) - self.forced_pages(flags)
        return FORCE_OCR_FLAG not in flags and bool(unforced)

    def _chapters_holding(self, file_pages: list[int]) -> set[int]:
        return {page for file_page in file_pages for page in self._chapter_of(file_page)}

    def _chapter_of(self, file_page: int) -> range:
        first = max([start for start in self._starts if start <= file_page], default=FIRST_PAGE)
        later = [start for start in self._starts if start > first]
        last = min(later) - 1 if later else self._page_count
        return range(first, last + 1)

    @staticmethod
    def forced_pages(flags: list[str]) -> set[int]:
        ranges = [flags[index + 1] for index, flag in enumerate(flags) if flag == FORCE_OCR_PAGES_FLAG]
        return {page for raw in ranges for page in PageRanges().parse(raw)}

    @staticmethod
    def _without_forced_pages(flags: list[str]) -> list[str]:
        forced_values = {index + 1 for index, flag in enumerate(flags) if flag == FORCE_OCR_PAGES_FLAG}
        return [flag for index, flag in enumerate(flags) if flag != FORCE_OCR_PAGES_FLAG and index not in forced_values]
