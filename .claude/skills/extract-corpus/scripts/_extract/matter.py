from __future__ import annotations

from _extract.firstlines import LayerFirstLines, MatterTitles
from _extract.outline import Heading

MAX_WHOLE_MATTER_RUN = 24


class MatterPages:
    def __init__(self, first_lines: LayerFirstLines, sections: list[tuple[Heading, int]]) -> None:
        self._first_lines = first_lines
        self._sections = sections
        self._titles = MatterTitles()

    def all(self) -> list[int]:
        content = [(heading, last) for heading, last in self._sections if self._holds_content(heading)]
        if not content:
            return []
        front = MatterRun(1, self._first_content_page([heading for heading, _last in content]))
        back = MatterRun(content[-1][1], self._first_lines.page_count())
        return front.pages(self._first_lines) + back.pages(self._first_lines)

    def _first_content_page(self, content: list[Heading]) -> int:
        last_front_matter = max(self._front_matter_openings(), default=0)
        after_front_matter = (heading.file_page for heading in content if heading.file_page > last_front_matter)
        return next(after_front_matter, content[0].file_page)

    def _front_matter_openings(self) -> list[int]:
        return [heading.file_page for heading, _last in self._sections
                if not self._holds_content(heading) and self._in_first_half(heading)]

    def _holds_content(self, heading: Heading) -> bool:
        return not self._titles.names_matter(heading.title)

    def _in_first_half(self, heading: Heading) -> bool:
        return 2 * heading.file_page <= self._first_lines.page_count()


class MatterRun:
    def __init__(self, first_page: int, last_page: int) -> None:
        self._first_page = first_page
        self._last_page = last_page

    def pages(self, first_lines: LayerFirstLines) -> list[int]:
        every_page = list(range(self._first_page, self._last_page + 1))
        if len(every_page) <= MAX_WHOLE_MATTER_RUN:
            return every_page
        return [self._first_page, *self._kind_changes(first_lines), self._last_page]

    def _kind_changes(self, first_lines: LayerFirstLines) -> list[int]:
        return [page for page in range(self._first_page + 1, self._last_page + 1)
                if first_lines.of(page).kind() != first_lines.of(page - 1).kind()]
