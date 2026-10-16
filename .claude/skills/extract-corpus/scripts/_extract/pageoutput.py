from __future__ import annotations

from _extract.candidates import OpenedHeadings
from _extract.elements import Heading, Paragraph
from _extract.footnotes import without_marks
from _extract.policy import SectionOpening, SectionPolicy
from _extract.spans import PagePlace


class PageOutput:
    def __init__(self, policy: SectionPolicy, opened: OpenedHeadings) -> None:
        self._policy = policy
        self._opened = opened
        self._elements: list = []
        self._raised_marks: list[str] = []

    def elements(self) -> list:
        return self._elements

    def is_empty(self) -> bool:
        return not self._elements

    def emit(self, elements: list) -> None:
        self._elements += elements

    def has_opened(self, title: str) -> bool:
        return self._opened.names(title)

    def hold_marks(self, marks: list[str]) -> None:
        self._raised_marks = list(marks)

    def raise_marks(self, marks: list[str]) -> None:
        self._raised_marks += marks

    def taken_marks(self) -> list[str]:
        marks, self._raised_marks = self._raised_marks, []
        return marks

    def open(self, heading: Heading, place: PagePlace) -> None:
        title, marks = without_marks(heading.title)
        marks += self.taken_marks()
        self._policy.opens(SectionOpening(heading.level, title, heading.key))
        if self._policy.keeps(place):
            self._opened.add(title, heading.level)
            self.emit([Heading(heading.level, title, heading.file_page, heading.key)])
            self.emit([Paragraph(" ".join(marks), False, heading.file_page)] if marks else [])
