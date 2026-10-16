from __future__ import annotations

import re
from collections import Counter

import vault
from _pagetext.folio import FOLIO_WORD_PATTERN
from page_marker import PageMarker

FLAG_ENTRY_LIST = "inside an entry list"
FLAG_FOOTNOTE_LOG = "named in the footnote log"
FLAG_BROKEN_PARAGRAPH = "a paragraph breaks off and the next opens in lowercase"
FLAG_EDGE_LINE = "a short line recurs at the edge of other pages"
FLAG_BARE_NUMERAL = "a bare numeral stands as a paragraph"
FLAG_FOOT_NOTE = "a numbered paragraph closes the page"
EDGE_LINE_WORDS = 8
MIN_EDGE_RECURRENCES = 3
FOOT_CHARS = 600
_HEADING_RE = re.compile(r"^#{1,6} (?P<title>.+)$")
_LOG_ENTRY_RE = re.compile(r"^file p\. (?P<page>\d+):")
_BREAKS_OFF_RE = re.compile(r"[a-z,;-]$")
_OPENS_LOWER_RE = re.compile(r"^[a-zà-öø-ÿ]")
_NUMERAL_RE = re.compile(FOLIO_WORD_PATTERN, re.IGNORECASE)
_FOOT_NOTE_RE = re.compile(r"\n\n(?:\d{1,3}|[*†‡])\s+[A-Z]")
_DIGITS_RE = re.compile(r"\d+")


class CleanupPages:
    def __init__(self, slices: dict[int, str], report: dict, running_on: frozenset[int] = frozenset()) -> None:
        self._slices = slices
        self._report = report
        self._running_on = running_on
        self._edges = Counter(edge for text in slices.values() for edge in _edges_of(text))

    def flagged(self) -> dict[int, list[str]]:
        logged = self._logged_pages()
        in_list = self._entry_list_pages()
        flags, last_paragraph = {}, ""
        for page, text in sorted(self._slices.items()):
            paragraphs = _paragraphs_of(text)
            across = page not in self._running_on and _runs_on_from(last_paragraph, paragraphs[:2])
            broken = across or _breaks_off(paragraphs[1:] if page in self._running_on else paragraphs)
            flags[page] = self._flags_of(text, paragraphs, (page in logged, page in in_list, broken))
            last_paragraph = paragraphs[-1] if paragraphs else last_paragraph
        return {page: reasons for page, reasons in flags.items() if reasons}

    def _flags_of(self, text: str, paragraphs: list[str], marks: tuple[bool, bool, bool]) -> list[str]:
        logged, in_list, broken = marks
        checks = ((in_list, FLAG_ENTRY_LIST), (logged, FLAG_FOOTNOTE_LOG), (broken, FLAG_BROKEN_PARAGRAPH),
                  (self._has_recurring_edge(text), FLAG_EDGE_LINE),
                  (any(_NUMERAL_RE.fullmatch(paragraph) for paragraph in paragraphs), FLAG_BARE_NUMERAL),
                  (bool(_FOOT_NOTE_RE.search(text[-FOOT_CHARS:])), FLAG_FOOT_NOTE))
        return [flag for holds, flag in checks if holds]

    def _has_recurring_edge(self, text: str) -> bool:
        return any(self._edges[edge] >= MIN_EDGE_RECURRENCES for edge in _edges_of(text))

    def _logged_pages(self) -> set[int]:
        matches = (_LOG_ENTRY_RE.match(entry) for entry in self._report.get("footnote_log") or [])
        return {int(match.group("page")) for match in matches if match}

    def _entry_list_pages(self) -> set[int]:
        pages, inside = set(), False
        for page, text in sorted(self._slices.items()):
            opened = inside and not text.lstrip().startswith("#")
            for title in _headings_of(text):
                inside = vault.is_bibliography_heading(title) or vault.is_notes_heading(title)
                opened = opened or inside
            if opened:
                pages.add(page)
        return pages


def pages_running_on(body: str) -> frozenset[int]:
    return frozenset(marker.file_page for start, _end, marker in PageMarker.located(body)
                     if marker.file_page is not None and body[:start].rstrip(" ") and not body[:start].endswith("\n"))


def _headings_of(text: str) -> list[str]:
    matches = (_HEADING_RE.match(line) for line in text.splitlines())
    return [match.group("title").strip() for match in matches if match]


def _edges_of(text: str) -> set[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    edges = lines[:1] + lines[-1:]
    return {_DIGITS_RE.sub("", line).strip().casefold() for line in edges
            if len(line.split()) <= EDGE_LINE_WORDS and _DIGITS_RE.sub("", line).strip()}


def _paragraphs_of(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]


def _runs_on_from(last_paragraph: str, openings: list[str]) -> bool:
    return bool(_BREAKS_OFF_RE.search(last_paragraph)) and any(_OPENS_LOWER_RE.match(opening) for opening in openings)


def _breaks_off(paragraphs: list[str]) -> bool:
    return any(_BREAKS_OFF_RE.search(before) and _OPENS_LOWER_RE.match(after)
               for before, after in zip(paragraphs, paragraphs[1:]))
