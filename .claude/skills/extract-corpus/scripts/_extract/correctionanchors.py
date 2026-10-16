from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

from page_marker import PageMarker

from _extract.correctiontext import Searchable, TrialText, Unit, normalized

MIN_ANCHOR_WORDS = 6
_HEADING_OPENING_RE = re.compile(r"^#{1,6} ")
_BOLD_RE = re.compile(r"^\*\*(?P<core>.+)\*\*$")
_WORD_RE = re.compile(r"\w+")


class CorrectionStale(Exception):
    pass


class CorrectionRefused(Exception):
    pass


class AnchorUnmatched(CorrectionRefused):
    pass


class LayerSource(Protocol):
    def lines(self, file_page: int) -> list[str]: ...

    def is_drawn(self, file_page: int) -> bool: ...


@dataclass(frozen=True)
class CorrectionContext:
    original: TrialText
    outline_titles: frozenset[str]
    layer: LayerSource

    def is_outline_title(self, title: str) -> bool:
        heading = normalized(title).casefold()
        return any(heading == known or heading.endswith(" " + known) for known in self.outline_titles)

    def knows(self, word: str) -> bool:
        return self._words[word.casefold()] > 0

    @cached_property
    def _words(self) -> Counter:
        return Counter(word.casefold() for word in _WORD_RE.findall(self.original.rendered()))


@dataclass(frozen=True)
class Found:
    index: int
    start: int
    end: int
    at_start: bool


class Anchors:
    def __init__(self, text: TrialText) -> None:
        self._text = text

    def in_body(self, page: int, anchor: str) -> Found:
        needle = normalized(anchor)
        found = self._found_in(self._body_indexes(page), needle)
        if len(needle.split()) < MIN_ANCHOR_WORDS and not self._is_whole(found, needle):
            raise CorrectionRefused(f"an anchor of fewer than {MIN_ANCHOR_WORDS} words must be a whole paragraph: "
                                    f"{anchor!r}")
        return found

    def span(self, page: int, quoted: str) -> Found:
        return self._found_in(self._body_indexes(page), normalized(quoted))

    def definition(self, anchor: str) -> Found:
        indexes = [index for index, unit in enumerate(self._text.units) if unit.in_notes]
        return self._found_in(indexes, normalized(anchor))

    def opening_marker(self, page: int) -> int:
        for index, unit in enumerate(self._text.units):
            if unit.is_marker_only and any(marker.file_page == page for _s, _e, marker in PageMarker.located(unit.text)):
                return index
        raise CorrectionRefused(f"page {page} opens inside a paragraph: name an anchor to place the text after")

    def _body_indexes(self, page: int) -> list[int]:
        pages = self._text.pages()
        return [index for index, unit in enumerate(self._text.units) if not unit.in_notes and page in pages[index]]

    def _found_in(self, indexes: list[int], needle: str) -> Found:
        hits = [hit for index in indexes for hit in self._hits_in(index, needle)]
        if not hits:
            raise AnchorUnmatched(f"the text matches nothing: {needle!r}")
        if len(hits) > 1:
            raise CorrectionRefused(f"the text matches {len(hits)} places: {needle!r}")
        return hits[0]

    def _hits_in(self, index: int, needle: str) -> list[Found]:
        searchable = Searchable(self._text.units[index].text)
        return [Found(index, searchable.origin(start), searchable.end_origin(start + len(needle)), start == 0)
                for start in searchable.find_all(needle)]

    def _is_whole(self, found: Found, needle: str) -> bool:
        return needle in (normalized(self._text.units[found.index].text), core_of(self._text.units[found.index]))


def core_of(unit: Unit) -> str:
    text = _HEADING_OPENING_RE.sub("", normalized(unit.text))
    bold = _BOLD_RE.match(text)
    return bold.group("core") if bold else text


def is_heading(unit: Unit) -> bool:
    return bool(_HEADING_OPENING_RE.match(unit.text.lstrip()))
