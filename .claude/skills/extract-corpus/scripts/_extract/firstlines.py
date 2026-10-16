from __future__ import annotations

import re
import unicodedata

from apparatus import Apparatus

from _extract.layer import TextLayer

FIRST_LINES = 6
ENTRY_WINDOW = 12
MIN_INDEX_ENTRIES = 3
MAX_UNSORTED_SHARE = 0.25
BLANK_KIND = "blank"
ENTRIES_KIND = "entries"
PROSE_KIND = "prose"
MATTER_CONTAINER_RE = re.compile(r"^((front|back|end)[- ]?matter|prelims|preliminary (pages|matter))$", re.IGNORECASE)
CONTROL_CHARACTERS_RE = re.compile(r"[\x00-\x1f\x7f]")
PAGE_REFERENCE_RE = re.compile(
    r"(?:^|[\s,;:])(?:\d{1,4}(?:[-–]\d{1,4})?|[ivxlc]{1,6})(?:\s?nn?\.?\s?\d{1,3})?(?:\s?ff?\.?)?,?$")


class LayerFirstLines:
    def __init__(self, layer: TextLayer) -> None:
        self._layer = layer
        self._pages: dict[int, FirstLines] = {}

    def of(self, file_page: int) -> FirstLines:
        if file_page not in self._pages:
            self._pages[file_page] = FirstLines(self._layer.text(file_page).splitlines())
        return self._pages[file_page]

    def page_count(self) -> int:
        return self._layer.page_count()


class FirstLines:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.strip() for line in lines if line.strip()]
        self._titles = MatterTitles()

    def kind(self) -> str:
        if not self._lines:
            return BLANK_KIND
        title = self._matter_title()
        if title is not None:
            return title.casefold()
        return ENTRIES_KIND if EntryLines(self._lines[:ENTRY_WINDOW]).dominate() else PROSE_KIND

    def opens_an_index(self) -> bool:
        heading = self._index_heading()
        if heading is None:
            return False
        following = heading + 1
        return EntryLines(self._lines[following:following + ENTRY_WINDOW]).alphabetized()

    def continues_an_index(self) -> bool:
        return self.opens_an_index() or EntryLines(self._lines[:ENTRY_WINDOW]).dominate()

    def _matter_title(self) -> str | None:
        return next((line for line in self._lines[:FIRST_LINES] if self._titles.names_matter(line)), None)

    def _index_heading(self) -> int | None:
        opening = self._lines[:FIRST_LINES]
        return next((number for number, line in enumerate(opening) if self._titles.names_index(line)), None)


class MatterTitles:
    def __init__(self) -> None:
        self._apparatus = Apparatus()

    def names_matter(self, title: str) -> bool:
        printed = _printed(title)
        return self._apparatus.is_apparatus(printed) or bool(MATTER_CONTAINER_RE.match(printed))

    def names_index(self, title: str) -> bool:
        return self._apparatus.is_index(_printed(title))


class EntryLines:
    def __init__(self, lines: list[str]) -> None:
        self._line_count = len(lines)
        self._entries = [line for line in lines if PAGE_REFERENCE_RE.search(line)]

    def dominate(self) -> bool:
        return 2 * len(self._entries) > self._line_count > 0

    def alphabetized(self) -> bool:
        initials = [_folded_initial(entry) for entry in self._entries if entry[0].isalpha()]
        if len(initials) < MIN_INDEX_ENTRIES:
            return False
        descents = sum(1 for earlier, later in zip(initials, initials[1:]) if later < earlier)
        return descents <= MAX_UNSORTED_SHARE * (len(initials) - 1)


def _printed(title: str) -> str:
    return CONTROL_CHARACTERS_RE.sub("", title).strip()


def _folded_initial(entry: str) -> str:
    return unicodedata.normalize("NFKD", entry[0]).casefold()[0]
