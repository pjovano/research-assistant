from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

from _extract.elements import Paragraph, Verbatim
from _extract.endnotes import EndnoteSections
from _extract.footnotes import mark_numbers
from _extract.notemarks import raised_mark_pattern


@dataclass(frozen=True)
class WithheldNote:
    file_page: int
    number: str
    is_endnote: bool


class WithheldMarks:
    def __init__(self, withheld: list[WithheldNote], sections: EndnoteSections) -> None:
        listed = sections.listed_numbers()
        self._endnotes = {note.number for note in withheld if note.is_endnote and note.number not in listed}
        self._footnotes = {(note.file_page, note.number) for note in withheld if not note.is_endnote}

    def removed(self, elements: list) -> list:
        return [self._without_marks(element) if isinstance(element, (Paragraph, Verbatim)) else element
                for element in elements]

    def _without_marks(self, element):
        numbers = [number for number in mark_numbers(element.text) if self._withholds(element.file_page, number)]
        text = element.text
        for number in numbers:
            text = re.sub(rf"\s*{raised_mark_pattern(number)}", "", text)
        return dataclasses.replace(element, text=text) if numbers else element

    def _withholds(self, file_page: int, number: str) -> bool:
        return number in self._endnotes or (file_page, number) in self._footnotes
