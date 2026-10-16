from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from citation_link import CITATION_LINK_RE
from page_marker import PageMarker

from _extract.writer import BLOCK_SEPARATOR, HEADING_MARK, NOTES_HEADING

NOTES_SECTION_OPENING = f"\n{HEADING_MARK} {NOTES_HEADING}{BLOCK_SEPARATOR}"
DEFINITION_OPENING = "[^"
NEW_NOTES_TAIL = "\n"
DEFINITION_SEPARATOR = "\n"
DEFINITION_RE = re.compile(r"^\[\^(?P<label>[^\]\s]+)\]:")
MARK_RE = re.compile(r"\[\^(?P<label>[^\]\s]+)\](?!:)")
NOTE_LABEL_RE = re.compile(r"\[\^[^\]\s]+\]:?")
_BLOCK_SPLIT_RE = re.compile(r"(\n{2,})")
_DEFINITION_SPLIT_RE = re.compile(r"(\n+)(?=\[\^[^\]\s]+\]:)")


@dataclass(frozen=True)
class Unit:
    text: str
    separator: str = BLOCK_SEPARATOR
    in_notes: bool = False

    @property
    def is_marker_only(self) -> bool:
        return not PageMarker.stripped(self.text, "").strip()

    @property
    def carries_a_marker(self) -> bool:
        return bool(PageMarker.located(self.text))

    @property
    def label(self) -> str | None:
        opening = DEFINITION_RE.match(self.text)
        return opening.group("label") if opening else None

    def with_text(self, text: str) -> Unit:
        return Unit(text, self.separator, self.in_notes)

    def with_separator(self, separator: str) -> Unit:
        return Unit(self.text, separator, self.in_notes)


class TrialText:
    def __init__(self, units: list[Unit], body_tail: str, notes_tail: str) -> None:
        self.units = units
        self._body_tail = body_tail
        self._notes_tail = notes_tail

    @classmethod
    def parsed(cls, body: str) -> TrialText:
        notes_start = body.rfind(NOTES_SECTION_OPENING + DEFINITION_OPENING)
        if notes_start < 0:
            body_part, notes_part = body, ""
        else:
            body_part, notes_part = body[:notes_start], body[notes_start + len(NOTES_SECTION_OPENING):]
        body_units, body_tail = _units(body_part, _BLOCK_SPLIT_RE, False)
        note_units, notes_tail = _units(notes_part, _DEFINITION_SPLIT_RE, True)
        return cls(body_units + note_units, body_tail, notes_tail)

    def rendered(self) -> str:
        body = _joined(self.body_units(), BLOCK_SEPARATOR)
        notes = self.definitions()
        if not notes:
            return body + self._body_tail
        notes_text = _joined(notes, DEFINITION_SEPARATOR) + self._notes_tail
        return body + (self._body_tail or NEW_NOTES_TAIL) + NOTES_SECTION_OPENING + notes_text

    def body_units(self) -> list[Unit]:
        return [unit for unit in self.units if not unit.in_notes]

    def definitions(self) -> list[Unit]:
        return [unit for unit in self.units if unit.in_notes]

    def letters(self) -> Counter:
        return letters_of(self.rendered())

    def pages(self) -> list[frozenset[int]]:
        return UnitPages(self.units).pages()

    def mark_pages(self) -> dict[str, set[int]]:
        return UnitPages(self.units).mark_pages()

    def marker_pages(self) -> list[int]:
        return [marker.file_page for unit in self.body_units() for _start, _end, marker in PageMarker.located(unit.text)
                if marker.file_page is not None]


class UnitPages:
    def __init__(self, units: list[Unit]) -> None:
        self._units = units

    def pages(self) -> list[frozenset[int]]:
        current: int | None = None
        pages: list[frozenset[int]] = []
        for unit in self._units:
            spans = self.segments(unit.text, current) if not unit.in_notes else []
            pages.append(frozenset(page for _offset, page in spans if page is not None))
            current = spans[-1][1] if spans else current
        return pages

    def mark_pages(self) -> dict[str, set[int]]:
        current: int | None = None
        found: dict[str, set[int]] = {}
        for unit in (unit for unit in self._units if not unit.in_notes):
            spans = self.segments(unit.text, current)
            for mark in MARK_RE.finditer(unit.text):
                found.setdefault(mark.group("label"), set()).add(self._page_at(spans, mark.start()))
            current = spans[-1][1] if spans else current
        return found

    @staticmethod
    def segments(text: str, current: int | None) -> list[tuple[int, int | None]]:
        located = PageMarker.located(text)
        opens_on_a_marker = bool(located) and not text[:located[0][0]].strip()
        spans = [] if opens_on_a_marker else [(0, current)]
        return spans + [(end, marker.file_page) for _start, end, marker in located]

    @staticmethod
    def _page_at(spans: list[tuple[int, int | None]], offset: int) -> int | None:
        page = None
        for start, span_page in spans:
            if start <= offset:
                page = span_page
        return page


class Searchable:
    def __init__(self, text: str) -> None:
        self._source = text
        self._characters: list[str] = []
        self._origins: list[int] = []
        self._pending_space = False
        hidden = _hidden_spans(text)
        index = 0
        while index < len(text):
            if index in hidden:
                index, self._pending_space = hidden[index], True
                continue
            self._take(text[index], index)
            index += 1
        self.text = "".join(self._characters)

    def _take(self, character: str, index: int) -> None:
        if character.isspace():
            self._pending_space = True
            return
        if self._pending_space and self._characters:
            self._characters.append(" ")
            self._origins.append(index)
        self._characters.append(character)
        self._origins.append(index)
        self._pending_space = False

    def find_all(self, needle: str) -> list[int]:
        found, start = [], self.text.find(needle)
        while needle and start >= 0:
            found.append(start)
            start = self.text.find(needle, start + 1)
        return found

    def origin(self, index: int) -> int:
        return self._origins[index] if index < len(self._origins) else len(self._source)

    def end_origin(self, end: int) -> int:
        return self._origins[end - 1] + 1 if end > 0 else 0


def normalized(text: str) -> str:
    return Searchable(text).text


def letters_of(text: str) -> Counter:
    unmarked = NOTE_LABEL_RE.sub(" ", CITATION_LINK_RE.sub(" ", PageMarker.stripped(text)))
    return Counter(character for character in unmarked if character.isalnum())


def _hidden_spans(text: str) -> dict[int, int]:
    spans = {start: end for start, end, _marker in PageMarker.located(text)}
    spans.update({match.start(): match.end() for match in CITATION_LINK_RE.finditer(text)})
    return spans


def _units(text: str, splitter: re.Pattern, in_notes: bool) -> tuple[list[Unit], str]:
    stripped = text.rstrip()
    tail = text[len(stripped):]
    if not stripped:
        return [], tail
    pieces = splitter.split(stripped)
    separators = [""] + pieces[1::2]
    return [Unit(piece, separator, in_notes) for piece, separator in zip(pieces[::2], separators)], tail


def _joined(units: list[Unit], default_separator: str) -> str:
    return "".join((unit.separator or default_separator if index else "") + unit.text
                   for index, unit in enumerate(units))
