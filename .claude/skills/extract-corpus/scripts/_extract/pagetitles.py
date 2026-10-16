from __future__ import annotations

import re
from pathlib import Path

import pagetext
from _pagetext.folio import FOLIO_WORD_PATTERN

from _extract.pagelabels import roman_value

BRACKETED_FOLIO = rf"[\[(]?\s*(?:{FOLIO_WORD_PATTERN})\s*[\])]?"
PAGE_REFERENCE_RE = re.compile(rf"^(?:p|pp|pg|page)\.?\s*{BRACKETED_FOLIO}$", re.IGNORECASE)
BARE_NUMERAL_RE = re.compile(rf"^{BRACKETED_FOLIO}$", re.IGNORECASE)
NUMERAL_RE = re.compile(rf"(?:{FOLIO_WORD_PATTERN})", re.IGNORECASE)
FOLIO_TOLERANCE = 1
MIN_NUMERAL_RUN = 2


class PageTitles:
    def __init__(self, pdf_path: Path, entries: list[tuple[str, int]]) -> None:
        self._pdf_path = pdf_path
        numerals = [(title.strip(), page) for title, page in entries if BARE_NUMERAL_RE.match(title.strip())]
        distances = [self._distance_from_the_folio(numeral, page) for numeral, page in numerals]
        judged = [distance for distance in distances if distance is not None]
        self._numerals_follow_the_folios = len(judged) >= MIN_NUMERAL_RUN and all(
            distance <= FOLIO_TOLERANCE for distance in judged)

    def names_a_page(self, title: str) -> bool:
        stripped = title.strip()
        if PAGE_REFERENCE_RE.match(stripped):
            return True
        return self._numerals_follow_the_folios and BARE_NUMERAL_RE.match(stripped) is not None

    def _distance_from_the_folio(self, numeral: str, file_page: int) -> int | None:
        folio = numeral_value(pagetext.printed_page_label(self._pdf_path, file_page))
        return None if folio is None else abs(folio - numeral_value(numeral))


def numeral_value(text: str | None) -> int | None:
    match = NUMERAL_RE.search(text or "")
    if match is None or BARE_NUMERAL_RE.match(text.strip()) is None:
        return None
    numeral = match.group(0)
    return int(numeral) if numeral.isdigit() else roman_value(numeral)
