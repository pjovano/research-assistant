from __future__ import annotations

from dataclasses import dataclass

import vault

from _extract.box import Box
from _extract.spans import ExcludedSpans, PagePlace, ScopeCut

is_notes_heading = vault.is_notes_heading
UNREAD_SIZE = 0.0


@dataclass(frozen=True)
class SectionOpening:
    level: int
    title: str
    key: tuple | None = None

    def sits_under(self, other: SectionOpening) -> bool:
        if self.level != other.level:
            return self.level > other.level
        return UNREAD_SIZE < self.type_size < other.type_size

    @property
    def type_size(self) -> float:
        return self.key[0] if self.key else UNREAD_SIZE


class SectionPolicy:
    def __init__(self, spans: ExcludedSpans) -> None:
        self._spans = spans
        self._entry_list: SectionOpening | None = None
        self._note_list = False

    @classmethod
    def keeping_everything(cls) -> SectionPolicy:
        return cls(ExcludedSpans.none())

    def opens(self, opening: SectionOpening) -> None:
        if self._opens_entry_list(opening.title):
            self._entry_list, self._note_list = opening, is_notes_heading(opening.title)
        elif self._entry_list is None or not opening.sits_under(self._entry_list):
            self._entry_list, self._note_list = None, False

    @staticmethod
    def _opens_entry_list(title: str) -> bool:
        return vault.is_bibliography_heading(title) or is_notes_heading(title)

    def keeps(self, place: PagePlace) -> bool:
        return not self._spans.excludes(place)

    def keeps_block(self, block) -> bool:
        return self.keeps_box(block.file_page, block.bbox)

    def keeps_box(self, file_page: int, box: Box) -> bool:
        height = box.bottom - box.top
        if height <= 0:
            return self.keeps(PagePlace(file_page, box.center[1]))
        return 2 * self._spans.covered_height(file_page, box) <= height

    def cuts_on(self, file_page: int) -> list[ScopeCut]:
        return self._spans.cuts(file_page)

    def resumed(self, place: PagePlace) -> PagePlace:
        return self._spans.resumed(place)

    def keeps_page(self, file_page: int) -> bool:
        return not self._spans.covers_page(file_page)

    @property
    def in_entry_list(self) -> bool:
        return self._entry_list is not None

    @property
    def in_note_list(self) -> bool:
        return self.in_entry_list and self._note_list
