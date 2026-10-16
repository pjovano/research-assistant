from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

from _extract.elements import Paragraph, Verbatim
from _extract.notemarks import raised_mark_pattern, written_mark


@dataclass(frozen=True)
class CarriedNote:
    mark_page: int
    number: str
    label: int

    def linked(self, text: str) -> str:
        return re.sub(raised_mark_pattern(self.number), written_mark(self.label),
                      text, count=1)


@dataclass(frozen=True)
class OpenMarks:
    file_page: int
    numbers: frozenset[str]

    def holds(self, number: str, file_page: int) -> bool:
        return self.file_page == file_page - 1 and number in self.numbers

    def without(self, closed: set[str]) -> OpenMarks:
        return OpenMarks(self.file_page, self.numbers - closed)


class UnansweredMarks:
    def __init__(self) -> None:
        self._mark_pages: dict[str, int] = {}

    def page_of(self, number: str) -> int | None:
        return self._mark_pages.get(number)

    def answer(self, number: str) -> None:
        self._mark_pages.pop(number, None)

    def withdraw(self, file_page: int, numbers: set[str]) -> None:
        for number in numbers:
            if self._mark_pages.get(number) == file_page:
                del self._mark_pages[number]

    def forget_all(self) -> None:
        self._mark_pages.clear()

    def keep(self, left_open: OpenMarks) -> None:
        self._mark_pages.update({number: left_open.file_page for number in left_open.numbers})


class CarriedMarks:
    def __init__(self, carried: list[CarriedNote]) -> None:
        self._carried = carried

    def linked(self, elements: list) -> list:
        return [self._linked(element) if isinstance(element, (Paragraph, Verbatim)) else element
                for element in elements]

    def _linked(self, element):
        text = element.text
        for note in self._carried:
            if note.mark_page == element.file_page:
                text = note.linked(text)
        return element if text == element.text else dataclasses.replace(element, text=text)
