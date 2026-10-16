from __future__ import annotations

import dataclasses

from _extract.blocks import HEADING_KIND, TEXT_KIND, PageBlocks
from _extract.headings import HeadingMatch
from _extract.outline import Heading as OutlineHeading
from _extract.policy import SectionPolicy
from _extract.runintitles import RunInTitle


class OutlinePlacement:
    def __init__(self, pages: list[PageBlocks], match: HeadingMatch, policy: SectionPolicy) -> None:
        self._titles = {page.file_page: [block.plain_text for block in page.content if block.kind == HEADING_KIND]
                        for page in pages}
        self._openings = {page.file_page: [block.plain_text for block in page.content if block.kind == TEXT_KIND]
                          for page in pages}
        self._match = match
        self._policy = policy

    def placed(self, headings: list[OutlineHeading]) -> list[OutlineHeading]:
        anchors = sorted({heading.file_page for heading in headings if self._prints_on_its_page(heading)})
        return [self._placed(heading, anchors) for heading in headings]

    def _placed(self, heading: OutlineHeading, anchors: list[int]) -> OutlineHeading:
        if self._prints_on_its_page(heading):
            return heading
        stretch = [file_page for file_page in self._stretch_around(heading.file_page, anchors)
                   if self._policy.keeps_page(file_page)]
        printing = self._pages_printing_as_a_heading(heading, stretch) or self._pages_opening_a_paragraph(heading, stretch)
        nearest = min(printing, key=lambda file_page: abs(file_page - heading.file_page), default=None)
        return heading if nearest is None else dataclasses.replace(heading, file_page=nearest)

    def _pages_printing_as_a_heading(self, heading: OutlineHeading, stretch: list[int]) -> list[int]:
        return [file_page for file_page in stretch if self._prints_any(self._titles.get(file_page, []), heading)]

    def _pages_opening_a_paragraph(self, heading: OutlineHeading, stretch: list[int]) -> list[int]:
        title = RunInTitle(heading.title)
        return [file_page for file_page in stretch if any(map(title.opens, self._openings.get(file_page, [])))]

    def _stretch_around(self, file_page: int, anchors: list[int]) -> range:
        first = max((anchor for anchor in anchors if anchor < file_page), default=min(self._titles, default=file_page))
        last = min((anchor for anchor in anchors if anchor > file_page), default=max(self._titles, default=file_page))
        return range(first, last + 1)

    def _prints_on_its_page(self, heading: OutlineHeading) -> bool:
        return self._prints_any(self._titles.get(heading.file_page, []), heading)

    def _prints_any(self, titles: list[str], heading: OutlineHeading) -> bool:
        return any(self._match.matches(title, heading.title) for title in titles)
