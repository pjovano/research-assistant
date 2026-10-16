from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pikepdf
import pymupdf

import vault

from .fonts import FontRecord
from .glyphs import is_suspect, marked
from .lines import RAW_DICTIONARY, Glyph, dictionary_lines
from .render import FIRST_PAGE
from .textkey import PLAIN_TEXT, TextLayerCacheEntry, TextLayerDigest, TextLayerKey

CONTEXT_CHARS = 60
LINE_SEPARATOR = " "
NO_BBOX = (0.0, 0.0, 0.0, 0.0)
OCCURRENCES_CACHE_NAME = vault.OCCURRENCES_CACHE_NAME
OCCURRENCES_VERSION = 3
NO_UNICODE = -1
MARKED_CONTENT_OPERATOR = "BDC"
ACTUAL_TEXT_KEY = "/ActualText"
PROPERTIES_KEY = "/Properties"


@dataclass(frozen=True)
class SuspectOccurrence:
    page: int
    font: str
    char: str
    line_bbox: tuple[float, float, float, float]
    context: str

    @property
    def page_number(self) -> int:
        return self.page + FIRST_PAGE

    @property
    def glyph(self) -> Glyph:
        return Glyph(self.font, self.char)

    def as_dict(self) -> dict:
        return {"page": self.page, "font": self.font, "char": self.char, "line_bbox": list(self.line_bbox),
                "context": self.context}

    @staticmethod
    def from_dict(row: dict) -> "SuspectOccurrence":
        bbox = tuple(float(edge) for edge in row["line_bbox"])
        return SuspectOccurrence(int(row["page"]), row["font"], row["char"], bbox, row["context"])


@dataclass(frozen=True)
class _Character:
    char: str
    font: str | None
    line_bbox: tuple[float, float, float, float]

    @property
    def glyph(self) -> Glyph:
        return Glyph(self.font, self.char)


class CachedOccurrences:
    def __init__(self, pdf_path: Path, wanted: frozenset[Glyph] = frozenset(),
                 digest: TextLayerDigest | None = None) -> None:
        self._source = TextLayerOccurrences(pdf_path, wanted)
        key = TextLayerKey(digest or TextLayerDigest(pdf_path), _stamp(wanted))
        self._entry = TextLayerCacheEntry(pdf_path, OCCURRENCES_CACHE_NAME, key)

    def collect(self) -> list[SuspectOccurrence]:
        rows = self._entry.load()
        if rows is not None:
            return [SuspectOccurrence.from_dict(row) for row in rows]
        found = self._source.collect()
        self._entry.save([occurrence.as_dict() for occurrence in found])
        return found


def _stamp(wanted: frozenset[Glyph]) -> list:
    return [OCCURRENCES_VERSION, sorted([glyph.font, glyph.char] for glyph in wanted)]


class TextLayerOccurrences:
    def __init__(self, pdf_path: Path, wanted: frozenset[Glyph] = frozenset()) -> None:
        self._path = pdf_path
        self._wanted = wanted
        self._wanted_chars = frozenset(glyph.char for glyph in wanted)

    def collect(self) -> list[SuspectOccurrence]:
        with pymupdf.open(self._path) as doc, pikepdf.open(self._path) as pdf:
            return [found for index, page in enumerate(doc) for found in self._on_page(index, page, pdf.pages[index])]

    def _on_page(self, index: int, page: pymupdf.Page, content: pikepdf.Page) -> list[SuspectOccurrence]:
        if not any(self._may_be_wanted(char) for char in page.get_text(PLAIN_TEXT)):
            return []
        substitutes = _SubstitutedCharacters(_drawn_glyphs(page), _actual_text_characters(content))
        return _PageCharacters(index, page.get_text(RAW_DICTIONARY),
                               lambda character: self._is_wanted(character)
                               and not substitutes.supplies(character)).occurrences()

    def _may_be_wanted(self, char: str) -> bool:
        return is_suspect(char) or char in self._wanted_chars

    def _is_wanted(self, character: _Character) -> bool:
        return is_suspect(character.char) or character.glyph in self._wanted


class _SubstitutedCharacters:
    def __init__(self, drawn: frozenset[Glyph], actual_text: frozenset[str]) -> None:
        self._drawn = drawn
        self._actual_text = actual_text

    def supplies(self, character: _Character) -> bool:
        return character.char in self._actual_text and character.glyph not in self._drawn


def _actual_text_characters(content: pikepdf.Page) -> frozenset[str]:
    properties = content.get("/Resources", {}).get(PROPERTIES_KEY, {})
    marked = (operands[1] for operands, operator in pikepdf.parse_content_stream(content)
              if str(operator) == MARKED_CONTENT_OPERATOR and len(operands) > 1)
    texts = (_actual_text(properties.get(str(entry), {}) if isinstance(entry, pikepdf.Name) else entry)
             for entry in marked)
    return frozenset(char for text in texts for char in text)


def _actual_text(entry: object) -> str:
    return str(entry.get(ACTUAL_TEXT_KEY, "")) if isinstance(entry, pikepdf.Dictionary) else ""


def _drawn_glyphs(page: pymupdf.Page) -> frozenset[Glyph]:
    return frozenset(Glyph(span["font"], chr(char[0])) for span in page.get_texttrace()
                     for char in span["chars"] if char[0] != NO_UNICODE)


class _PageCharacters:
    def __init__(self, page_index: int, raw: dict, is_wanted: Callable[[_Character], bool]) -> None:
        self._page = page_index
        self._characters = _flattened(raw)
        self._is_wanted = is_wanted

    def occurrences(self) -> list[SuspectOccurrence]:
        return [self._occurrence(position, character)
                for position, character in enumerate(self._characters)
                if character.font is not None and self._is_wanted(character)]

    def _occurrence(self, position: int, character: _Character) -> SuspectOccurrence:
        return SuspectOccurrence(self._page, character.font, character.char, character.line_bbox,
                                 self._context(position))

    def _context(self, position: int) -> str:
        start = max(0, position - CONTEXT_CHARS)
        end = position + 1 + CONTEXT_CHARS
        return "".join(self._shown(character) for character in self._characters[start:end])

    def _shown(self, character: _Character) -> str:
        return marked(character.char) if self._is_wanted(character) else character.char


def _flattened(raw: dict) -> list[_Character]:
    characters: list[_Character] = []
    for line in dictionary_lines(raw):
        characters.extend(_line_characters(line))
        characters.append(_Character(LINE_SEPARATOR, None, NO_BBOX))
    return characters


def _line_characters(line: dict) -> list[_Character]:
    bbox = tuple(line["bbox"])
    return [_Character(char["c"], span["font"], bbox) for span in line["spans"] for char in span["chars"]]


class Occurrences:
    def __init__(self, found: list[SuspectOccurrence], gathered: frozenset[Glyph] = frozenset()) -> None:
        self._found = found
        self._gathered = gathered
        self._by_font_and_char: dict[tuple[str, str], list[SuspectOccurrence]] = {}
        for occurrence in found:
            self._by_font_and_char.setdefault((occurrence.font, occurrence.char), []).append(occurrence)

    def gathers(self, record: FontRecord, char: str) -> bool:
        return is_suspect(char) or Glyph(record.text_layer_name, char) in self._gathered

    def of(self, record: FontRecord, char: str) -> list[SuspectOccurrence]:
        candidates = self._by_font_and_char.get((record.text_layer_name, char), [])
        return [found for found in candidates if record.uses_page(found.page)]

    def of_font(self, record: FontRecord) -> list[SuspectOccurrence]:
        return [found for found in self._found if found.font == record.text_layer_name and record.uses_page(found.page)]

    def matching(self, glyphs: set[Glyph]) -> list[SuspectOccurrence]:
        return [found for found in self._found if found.glyph in glyphs]
