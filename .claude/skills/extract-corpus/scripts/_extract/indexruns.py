from __future__ import annotations

from _extract.enginelabels import LabelledRun
from _extract.firstlines import LayerFirstLines, MatterTitles
from _extract.outline import Heading

INDEX_LABEL = "index"


class IndexRuns:
    def __init__(self, first_lines: LayerFirstLines, headings: list[Heading]) -> None:
        self._first_lines = first_lines
        self._headings = headings

    def runs(self) -> list[LabelledRun]:
        runs: list[LabelledRun] = []
        for opening in self._openings():
            if not runs or opening > runs[-1].last_page:
                runs.append(LabelledRun(opening, self._last_index_page(opening), INDEX_LABEL))
        return runs

    def _openings(self) -> list[int]:
        titles = MatterTitles()
        named = {heading.file_page for heading in self._headings if titles.names_index(heading.title)}
        printed = {page for page in self._all_pages() if self._first_lines.of(page).opens_an_index()}
        return sorted(named | printed)

    def _last_index_page(self, opening: int) -> int:
        last = opening
        while last < self._first_lines.page_count() and self._first_lines.of(last + 1).continues_an_index():
            last += 1
        return last

    def _all_pages(self) -> range:
        return range(1, self._first_lines.page_count() + 1)
