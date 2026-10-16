from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from text_layer_spaces import takes_no_advance

RAW_DICTIONARY = "rawdict"
LINE_SEPARATOR = "\n"
SUBSET_PREFIX_RE = re.compile(r"^[A-Z]{6}\+")
MATH_FONT_PREFIXES = (
    "cmmi", "cmsy", "cmex", "cmbsy", "cmmib", "mtmi", "mtsy", "mtex", "mathtime", "stmary", "wasy", "msam", "msbm",
    "eufm", "eufb", "eusm", "eusb", "eurm", "eurb", "lasy", "pazomath", "mathematicalpi", "symbol", "rsfs", "esint",
    "txsy", "txmi", "txex", "pxsy", "pxmi", "pxex", "esstix",
)
MATH_NAME_TOKEN_RE = re.compile(r"Math(?![a-z])")
DRAWN_FONT = "VaultDrawn"
MIN_OUTSIDE_SHARE = 0.5
MIN_SPANS_FOR_MEASURE = 20
MIN_SINGLE_SPAN_SHARE = 0.85
MIN_LETTER_SHARE = 0.5
MAX_WORK_SHARE = 0.05
PROSE_CATEGORIES = ("L", "N", "P", "Z")
MATH_SYMBOL_CATEGORY = "Sm"
LETTER_CATEGORY = "L"
COMPATIBILITY_DECOMPOSITION = "NFKD"


def is_listed_math_font(font: str) -> bool:
    family = SUBSET_PREFIX_RE.sub("", font)
    return family.casefold().startswith(MATH_FONT_PREFIXES) or MATH_NAME_TOKEN_RE.search(family) is not None


@dataclass
class FontCensus:
    chars: Counter = field(default_factory=Counter)
    spans: int = 0
    single_spans: int = 0

    def add_span(self, text: str) -> None:
        inked = text.replace(" ", "")
        self.chars.update(inked)
        if inked:
            self.spans += 1
            self.single_spans += len(inked) == 1

    @property
    def occurrences(self) -> int:
        return sum(self.chars.values())

    def outside_share(self) -> float:
        outside = sum(count for char, count in self.chars.items() if not _is_prose_character(char))
        return outside / max(self.occurrences, 1)

    def letter_share(self) -> float:
        letters = sum(count for char, count in self.chars.items()
                      if unicodedata.category(char).startswith(LETTER_CATEGORY))
        return letters / max(self.occurrences, 1)

    def single_letter_share(self) -> float:
        single_letters = sum(count for char, count in self.chars.items()
                             if unicodedata.category(char).startswith(LETTER_CATEGORY) and not _is_ligature(char))
        return single_letters / max(self.occurrences, 1)

    def is_symbols_without_letters(self) -> bool:
        return self.letter_share() == 0.0 and any(_is_math_symbol(char) for char in self.chars)

    def is_set_one_glyph_at_a_time(self) -> bool:
        return self.spans >= MIN_SPANS_FOR_MEASURE and self.single_spans / self.spans >= MIN_SINGLE_SPAN_SHARE


def _is_math_symbol(char: str) -> bool:
    return unicodedata.category(char) == MATH_SYMBOL_CATEGORY


def _is_prose_character(char: str) -> bool:
    return unicodedata.category(char).startswith(PROSE_CATEGORIES)


def _is_ligature(char: str) -> bool:
    decomposed = unicodedata.normalize(COMPATIBILITY_DECOMPOSITION, char)
    return sum(unicodedata.category(part).startswith(LETTER_CATEGORY) for part in decomposed) > 1


class MathFonts:
    def __init__(self, pdf_path: Path) -> None:
        self._path = Path(pdf_path)
        self._census: dict[str, FontCensus] | None = None
        self._families: set[str] | None = None

    def families(self) -> list[str]:
        return sorted(self._math_families())

    def is_math(self, font: str) -> bool:
        return font == DRAWN_FONT or font in self._math_families()

    def notation_characters(self) -> set[str]:
        census = self._counted()
        in_prose = {char for font, counted in census.items() if not self.is_math(font) for char in counted.chars}
        in_math = {char for font, counted in census.items() if self.is_math(font) for char in counted.chars}
        return in_math - in_prose

    def prose_text(self, file_page: int) -> str:
        with pymupdf.open(self._path) as document:
            return self._prose_page(document[file_page - 1])

    def prose_texts(self) -> list[tuple[int, str]]:
        with pymupdf.open(self._path) as document:
            return [(index + 1, self._prose_page(page)) for index, page in enumerate(document)]

    def _prose_page(self, page) -> str:
        return LINE_SEPARATOR.join(self._prose_of(line) for line in _lines_of(page.get_text(RAW_DICTIONARY)))

    def _prose_of(self, line: dict) -> str:
        fonts = [span["font"] for span in line["spans"] for _char in span["chars"]]
        chars = [char for span in line["spans"] for char in span["chars"]]
        return "".join(char["c"] for index, char in enumerate(chars) if self._is_prose(chars, index, fonts[index]))

    def _is_prose(self, chars: list[dict], index: int, font: str) -> bool:
        if chars[index]["c"].isspace():
            return not takes_no_advance(chars, index)
        return not self.is_math(font)

    def _math_families(self) -> set[str]:
        if self._families is None:
            self._families = {font for font, counted in self._counted().items() if self._judged_math(font, counted)}
        return self._families

    def _judged_math(self, font: str, counted: FontCensus) -> bool:
        if is_listed_math_font(font):
            return True
        if counted.outside_share() >= MIN_OUTSIDE_SHARE or counted.is_symbols_without_letters():
            return True
        return self._is_variable_font(counted)

    def _is_variable_font(self, counted: FontCensus) -> bool:
        small_share = counted.occurrences <= MAX_WORK_SHARE * self._work_occurrences()
        sets_variables = counted.single_letter_share() >= MIN_LETTER_SHARE
        return counted.is_set_one_glyph_at_a_time() and sets_variables and small_share

    def _work_occurrences(self) -> int:
        return sum(counted.occurrences for counted in self._counted().values())

    def _counted(self) -> dict[str, FontCensus]:
        if self._census is None:
            self._census = _FontReader(self._path).census()
        return self._census


class _FontReader:
    def __init__(self, pdf_path: Path) -> None:
        self._path = pdf_path

    def census(self) -> dict[str, FontCensus]:
        census: dict[str, FontCensus] = {}
        with pymupdf.open(self._path) as document:
            for page in document:
                self._count_page(page.get_text(RAW_DICTIONARY), census)
        return census

    def _count_page(self, raw: dict, census: dict[str, FontCensus]) -> None:
        for line in _lines_of(raw):
            for span in line["spans"]:
                census.setdefault(span["font"], FontCensus()).add_span("".join(char["c"] for char in span["chars"]))


def _lines_of(raw: dict) -> list[dict]:
    return [line for block in raw["blocks"] for line in block.get("lines", [])]
