from __future__ import annotations

from dataclasses import dataclass, field

from _extract.elements import Heading, Paragraph, Verbatim
from _extract.notenumbers import CORPUS_ENTRY_OPENING_RE
from _extract.policy import is_notes_heading


@dataclass
class EndnoteSection:
    level: int
    first_page: int
    last_page: int
    numbers: set[str] = field(default_factory=set)

    def holds_page(self, file_page: int) -> bool:
        return self.first_page <= file_page <= self.last_page

    def take(self, element) -> None:
        self.last_page = max(self.last_page, element.file_page)
        number = CORPUS_ENTRY_OPENING_RE.match(element.text) if isinstance(element, (Paragraph, Verbatim)) else None
        if number:
            self.numbers.add(number.group(1))


class EndnoteSections:
    def __init__(self, elements: list) -> None:
        self._sections: list[EndnoteSection] = []
        self._open: EndnoteSection | None = None
        for element in elements:
            self._read(element)

    def lists_mark(self, file_page: int, number: str) -> bool:
        following = next((section for section in self._sections if section.last_page >= file_page), None)
        return following is not None and number in following.numbers

    def holds_page(self, file_page: int) -> bool:
        return any(section.holds_page(file_page) for section in self._sections)

    def listed_numbers(self) -> set[str]:
        return {number for section in self._sections for number in section.numbers}

    def _read(self, element) -> None:
        if isinstance(element, Heading):
            self._read_heading(element)
        elif self._open is not None and hasattr(element, "file_page"):
            self._open.take(element)

    def _read_heading(self, heading: Heading) -> None:
        if self._open is not None and heading.level <= self._open.level:
            self._open = None
        if is_notes_heading(heading.title):
            self._open = EndnoteSection(heading.level, heading.file_page, heading.file_page)
            self._sections.append(self._open)
