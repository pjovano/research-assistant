from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from .spans import SIGLUM, WordGrid

OCR_PAGE_NUMBER = r"[0-9][0-9Oo]{0,2}"
VOLUME_NUMBER = r"\d{1,2}"
SIGLUM_REFERENCE = re.compile(rf"(?P<siglum>{SIGLUM})\s?(?P<number>{OCR_PAGE_NUMBER})")
VOLUME_REFERENCE = re.compile(rf"(?P<volume>{VOLUME_NUMBER})\s?:\s?(?P<number>{OCR_PAGE_NUMBER})")
EDITION_REFERENCE = rf"(?:{SIGLUM}\s?{OCR_PAGE_NUMBER}|{VOLUME_NUMBER}\s?:\s?{OCR_PAGE_NUMBER})"
REFERENCE_SEPARATOR = "/"
BRACKETED_PAGINATION = re.compile(
    rf"\[\s?(?P<references>{EDITION_REFERENCE}(?:\s?{REFERENCE_SEPARATOR}\s?{EDITION_REFERENCE})*)\s?\]")
FORM_COMBINED = "combined"
FORM_SINGLE = "single"
FORM_AKADEMIE = "akademie"
BARE_NUMBER = re.compile(r"^\d{1,4}$")

MARGINAL_MIN_GAP = 4.0
AKADEMIE_PREFIX = "Ak"

STRATEGY_INLINE_MARKER = "inline-marker"
STRATEGY_MARGINAL_NUMBER = "marginal-number"
STRATEGY_QUOTE_MATCH = "quote-match"


@dataclass(frozen=True)
class EditionMarker:
    page: int
    word_index: int
    edition: str
    number: int
    form: str

    @staticmethod
    def labelled(edition: str, number: int) -> str:
        if edition.startswith(AKADEMIE_PREFIX):
            return f"{edition.removeprefix(AKADEMIE_PREFIX)}:{number}"
        return f"{edition}{number}"

    @property
    def label(self) -> str:
        return self.labelled(self.edition, self.number)


class MarkerNumber:
    @staticmethod
    def parsed(raw: str) -> int:
        return int(raw.replace("O", "0").replace("o", "0"))


class MarkerGrammar:
    def scan(self, text: str) -> list[tuple[str, int, int, str]]:
        return [marker for match in BRACKETED_PAGINATION.finditer(text)
                for marker in BracketedPagination(match).markers()]


class BracketedPagination:
    def __init__(self, match: re.Match) -> None:
        self._references = [reference.strip() for reference in match.group("references").split(REFERENCE_SEPARATOR)]
        self._offset = match.start()

    def markers(self) -> list[tuple[str, int, int, str]]:
        return [self._marker(reference) for reference in self._references]

    def _marker(self, reference: str) -> tuple[str, int, int, str]:
        volume = VOLUME_REFERENCE.fullmatch(reference)
        if volume is not None:
            return self._volume_marker(volume)
        return self._siglum_marker(SIGLUM_REFERENCE.fullmatch(reference))

    def _volume_marker(self, volume: re.Match) -> tuple[str, int, int, str]:
        edition = f"{AKADEMIE_PREFIX}{volume.group('volume')}"
        return edition, MarkerNumber.parsed(volume.group("number")), self._offset, self._form(FORM_AKADEMIE)

    def _siglum_marker(self, siglum: re.Match) -> tuple[str, int, int, str]:
        return (siglum.group("siglum"), MarkerNumber.parsed(siglum.group("number")), self._offset,
                self._form(FORM_SINGLE))

    def _form(self, form_alone: str) -> str:
        if len(self._references) > 1:
            return FORM_COMBINED
        return form_alone


class PageGrids:
    def __init__(self, document) -> None:
        self._document = document
        self._grids: dict[int, WordGrid] = {}

    def numbered(self) -> list[tuple[int, WordGrid]]:
        return [(number, self.of(number)) for number in range(1, self._document.page_count + 1)]

    def of(self, page_number: int) -> WordGrid:
        if page_number not in self._grids:
            self._grids[page_number] = WordGrid(self._document[page_number - 1])
        return self._grids[page_number]


class InlineMarkerIndex:
    def __init__(self, grids: PageGrids) -> None:
        self._markers = self._build(grids)

    @property
    def markers(self) -> list[EditionMarker]:
        return list(self._markers)

    @property
    def is_available(self) -> bool:
        return bool(self._markers)

    def coverage(self) -> dict[str, int]:
        return Counter(marker.form for marker in self._markers)

    def resolve(self, edition: str, number: int) -> list[EditionMarker]:
        return [m for m in self._markers if m.edition == edition and m.number == number]

    def bracketing(self, edition: str, number: int) -> tuple:
        ordered = sorted([m for m in self._markers if m.edition == edition],
                         key=lambda m: m.number)
        below = [m for m in ordered if m.number <= number]
        above = [m for m in ordered if m.number > number]
        return (below[-1] if below else None, above[0] if above else None)

    def _build(self, grids: PageGrids) -> list[EditionMarker]:
        grammar = MarkerGrammar()
        return [marker for page_number, grid in grids.numbered()
                for marker in self._page_markers(grammar, grid, page_number)]

    def _page_markers(self, grammar: MarkerGrammar, grid: WordGrid, page_number: int) -> list[EditionMarker]:
        return [EditionMarker(page_number, grid.index_at(offset), edition, value, form)
                for edition, value, offset, form in grammar.scan(grid.joined())]


class MarginalNumberIndex:
    def __init__(self, grids: PageGrids) -> None:
        self._numbers = self._build(grids)

    @property
    def is_available(self) -> bool:
        return bool(self._numbers)

    def resolve(self, number: int) -> list[tuple[int, int]]:
        return [(page, index) for page, index, value in self._numbers if value == number]

    def _build(self, grids: PageGrids) -> list[tuple[int, int, int]]:
        return [number for page_number, grid in grids.numbered()
                for number in self._page_numbers(grid, page_number)]

    def _page_numbers(self, grid: WordGrid, page_number: int) -> list[tuple[int, int, int]]:
        column = grid.column()
        if column is None:
            return []
        return [(page_number, box.index, int(box.text))
                for box in grid.boxes if self._is_marginal(box, column)]

    def _is_marginal(self, box, column) -> bool:
        if not BARE_NUMBER.match(box.text):
            return False
        return (box.x0 > column.right + MARGINAL_MIN_GAP or
                box.x1 < column.left - MARGINAL_MIN_GAP)


class EditionAnchorIndex:
    def __init__(self, pdf_path) -> None:
        with pymupdf.open(pdf_path) as document:
            grids = PageGrids(document)
            self._inline = InlineMarkerIndex(grids)
            self._marginal = MarginalNumberIndex(grids)

    @property
    def inline(self) -> InlineMarkerIndex:
        return self._inline

    @property
    def marginal(self) -> MarginalNumberIndex:
        return self._marginal

    def strategies(self) -> list[str]:
        available = []
        if self._inline.is_available:
            available.append(STRATEGY_INLINE_MARKER)
        if self._marginal.is_available:
            available.append(STRATEGY_MARGINAL_NUMBER)
        available.append(STRATEGY_QUOTE_MATCH)
        return available
