from __future__ import annotations

import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from confusables import compatible

RAW_DICTIONARY = "rawdict"
LATIN_LIMIT = 0x0250
PLAIN_CATEGORIES = ("L", "N", "P")


@dataclass(frozen=True)
class Glyph:
    font: str
    char: str

    def is_blank(self) -> bool:
        return self.char.isspace()

    def is_plain(self) -> bool:
        return ord(self.char) < LATIN_LIMIT and unicodedata.category(self.char).startswith(PLAIN_CATEGORIES)

    def is_symbol(self) -> bool:
        return not self.is_blank() and not self.is_plain()

    def folded(self) -> str:
        return compatible(self.char)


@dataclass(frozen=True)
class TextLine:
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    fonts: tuple[str, ...]

    def glyphs(self) -> list[Glyph]:
        return [Glyph(font, char) for font, char in zip(self.fonts, self.text)]

    def distinct_glyphs(self) -> set[Glyph]:
        return {glyph for glyph in self.glyphs() if not glyph.is_blank()}


class TextLines:
    def __init__(self, pdf_path: Path) -> None:
        self._path = pdf_path

    def collect(self) -> list[TextLine]:
        with pymupdf.open(self._path) as doc:
            return [line for index, page in enumerate(doc)
                    for line in _page_lines(index, page.get_text(RAW_DICTIONARY))]


def dictionary_lines(text_dictionary: dict) -> list[dict]:
    return [line for block in text_dictionary["blocks"] for line in block.get("lines", [])]


def _page_lines(page_index: int, raw: dict) -> list[TextLine]:
    return [_line(page_index, line) for line in dictionary_lines(raw)]


def _line(page_index: int, line: dict) -> TextLine:
    characters = [(sys.intern(span["font"]), char["c"]) for span in line["spans"] for char in span["chars"]]
    text = "".join(char for _, char in characters)
    return TextLine(page_index, tuple(line["bbox"]), text, tuple(font for font, _ in characters))
