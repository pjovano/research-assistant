from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import vault
from conversion_cache_keys import CachedConversionsKept
from page_marker import PageMarker

from _extract.failures import UsageFailure
from _extract.paths import CorpusFile

STYLE_DECIMAL = "D"
STYLE_ROMAN_LOWER = "r"
STYLE_ROMAN_UPPER = "R"
STYLE_NONE = ""
FIRST_FILE_PAGE = 1
LABEL_TEMPORARY_SUFFIX = ".labels-partial"
_NUMBERED_FOLIO_RE = re.compile(r"^(?P<prefix>.*?)(?P<digits>\d+|(?P<lower>[ivxlcdm]+)|(?P<upper>[IVXLCDM]+))$")
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


class LabelsRefused(UsageFailure, ValueError):
    pass


def roman_value(numeral: str) -> int:
    values = [_ROMAN_VALUES[char] for char in numeral.lower()]
    return sum(-value if index + 1 < len(values) and value < values[index + 1] else value
               for index, value in enumerate(values))


@dataclass(frozen=True)
class FolioParts:
    prefix: str
    style: str
    number: int

    @classmethod
    def of(cls, folio: str | None) -> FolioParts:
        if folio is None:
            return cls("", STYLE_NONE, 0)
        match = _NUMBERED_FOLIO_RE.match(folio)
        if match is None:
            return cls(folio, STYLE_NONE, 0)
        return cls(match.group("prefix"), cls._style(match), cls._number(match))

    @staticmethod
    def _style(match: re.Match) -> str:
        if match.group("lower"):
            return STYLE_ROMAN_LOWER
        return STYLE_ROMAN_UPPER if match.group("upper") else STYLE_DECIMAL

    @staticmethod
    def _number(match: re.Match) -> int:
        digits = match.group("digits")
        return int(digits) if digits.isdigit() else roman_value(digits)

    def follows(self, previous: FolioParts) -> bool:
        same_run = (self.prefix, self.style) == (previous.prefix, previous.style)
        return same_run and (self.style == STYLE_NONE or self.number == previous.number + 1)


@dataclass(frozen=True)
class LabelRange:
    start_page: int
    parts: FolioParts

    def as_dict(self) -> dict:
        return {"startpage": self.start_page - 1, "prefix": self.parts.prefix, "style": self.parts.style,
                "firstpagenum": self.parts.number}


class LabelRanges:
    def __init__(self, folios: dict[int, str | None], page_count: int) -> None:
        self._folios = folios
        self._page_count = page_count

    def all(self) -> list[LabelRange]:
        ranges: list[LabelRange] = []
        previous = None
        for file_page in range(FIRST_FILE_PAGE, self._page_count + 1):
            parts = FolioParts.of(self._folios.get(file_page))
            if previous is None or not parts.follows(previous):
                ranges.append(LabelRange(file_page, parts))
            previous = parts
        return ranges


class PageLabelWriter:
    def __init__(self, pdf_path: Path, note: CorpusFile) -> None:
        self._pdf_path = pdf_path
        self._note = note

    def plan(self) -> dict:
        self._require_labellable()
        folios = {marker.file_page: marker.folio for marker in reversed(PageMarker.inline(self._note.body()))}
        with pymupdf.open(self._pdf_path) as document:
            ranges = LabelRanges(folios, document.page_count).all()
            return {"pdf": self._pdf_path.name, "pages": document.page_count,
                    "labelled_pages": sum(1 for folio in folios.values() if folio),
                    "current": document.get_page_labels(), "planned": [found.as_dict() for found in ranges]}

    def _require_labellable(self) -> None:
        if self._note.frontmatter().get(vault.UNCITABLE_FIELD):
            raise LabelsRefused(f"{self._note.basename} carries {vault.UNCITABLE_FIELD}: the held copy's folios cannot "
                                "be checked, so no page labels are written")
        if not self._note.has_body():
            raise LabelsRefused(f"{self._note.basename} has no corpus file body; run accept first")

    def apply(self, plan: dict) -> list[dict]:
        with CachedConversionsKept(self._pdf_path):
            with vault.ReplacementFile(self._pdf_path, LABEL_TEMPORARY_SUFFIX) as replacement:
                self._write(plan["planned"], replacement.path)
                replacement.commit()
        with pymupdf.open(self._pdf_path) as document:
            return document.get_page_labels()

    def _write(self, ranges: list[dict], destination: Path) -> None:
        with pymupdf.open(self._pdf_path) as document:
            document.set_page_labels(ranges)
            document.save(destination)
