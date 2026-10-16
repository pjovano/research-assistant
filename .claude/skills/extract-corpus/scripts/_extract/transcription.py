from __future__ import annotations

from typing import Callable

from _extract.elements import Heading, Paragraph
from _extract.headings import HeadingMatch
from _extract.outline import Heading as OutlineHeading


class TranscribedBody:
    def __init__(self, text: str, file_page: int, match: HeadingMatch) -> None:
        self._lines = text.splitlines()
        self._file_page = file_page
        self._match = match

    def elements(self, due: list[OutlineHeading], opened: Callable[[OutlineHeading], Heading]) -> list:
        elements: list = []
        remaining = self._lines
        for heading in due:
            opening = self._opening_of(remaining, heading.title)
            if opening is not None:
                elements += self._paragraphs(remaining[:opening])
                remaining = remaining[opening + 1:]
            elements.append(opened(heading))
        return elements + self._paragraphs(remaining)

    def _paragraphs(self, lines: list[str]) -> list:
        return [Paragraph(line.strip(), False, self._file_page) for line in lines if line.strip()]

    def _opening_of(self, lines: list[str], title: str) -> int | None:
        return next((index for index, line in enumerate(lines) if self._match.matches(line.strip(), title)), None)
