from __future__ import annotations

import re

from _vault.citations import is_bibliography_heading, is_notes_heading
from _vault.markdown import FOOTNOTE_DEFINITION_RE, HEADING_RE, OBSIDIAN_COMMENT_RE

_COMMENT_REPLACEMENT = " "


class _HeadingLine:
    def __init__(self, index: int, match: re.Match) -> None:
        self.index = index
        self.level = len(match.group("hashes"))
        self.text = OBSIDIAN_COMMENT_RE.sub(_COMMENT_REPLACEMENT, match.group("text")).strip()

    @property
    def is_bibliography(self) -> bool:
        return is_bibliography_heading(self.text)

    @property
    def is_entry_list(self) -> bool:
        return self.is_bibliography or is_notes_heading(self.text)

    def is_at_or_above(self, level: int) -> bool:
        return self.level <= level


class _HeadingSpans:
    def __init__(self, lines: list[str], selects) -> None:
        self._selects = selects
        self._end_of_body = len(lines)
        self._headings = [_HeadingLine(index, match) for index, match in self._matched(lines, HEADING_RE)]
        self._footnotes = [index for index, _match in self._matched(lines, FOOTNOTE_DEFINITION_RE)]

    @staticmethod
    def _matched(lines: list[str], pattern: re.Pattern) -> list[tuple[int, re.Match]]:
        matches = ((index, pattern.match(line)) for index, line in enumerate(lines))
        return [(index, match) for index, match in matches if match is not None]

    def all(self) -> list[tuple[int, int]]:
        return [self._span(position) for position, heading in enumerate(self._headings) if self._selects(heading)]

    def _span(self, position: int) -> tuple[int, int]:
        start = self._headings[position].index
        return start, min(self._next_heading_at_or_above(position), self._next_footnote_after(start))

    def _next_heading_at_or_above(self, position: int) -> int:
        level = self._headings[position].level
        followers = self._headings[position + 1:]
        return next((heading.index for heading in followers if heading.is_at_or_above(level)), self._end_of_body)

    def _next_footnote_after(self, start: int) -> int:
        return next((index for index in self._footnotes if index > start), self._end_of_body)


class BibliographySpan:
    def __init__(self, lines: list[str]) -> None:
        self._spans = _HeadingSpans(lines, lambda heading: heading.is_bibliography)

    def all(self) -> list[tuple[int, int]]:
        return self._spans.all()


class EntryListSpans:
    def __init__(self, lines: list[str]) -> None:
        self._spans = _HeadingSpans(lines, lambda heading: heading.is_entry_list)

    def all(self) -> list[tuple[int, int]]:
        return self._spans.all()
