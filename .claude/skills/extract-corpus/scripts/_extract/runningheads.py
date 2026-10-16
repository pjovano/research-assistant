from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from _pagetext.folio import FOLIO_WORD_PATTERN
from pagetext import TOP_LEVEL

from _extract.box import Box
from _extract.headings import HeadingMatch, section_number_of, shape_of
from _extract.layercolumns import STYLE_SIZE_TOLERANCE_POINTS

REPEATED_PAGES = 2
DISPLAY_TYPE_RATIO = 1.2
_DIGIT_RE = re.compile(r"\d+")
_FOLIO = rf"(?P<folio>{FOLIO_WORD_PATTERN})"
_FOLIO_PREFIX_RE = re.compile(rf"^\s*{_FOLIO}\s+(?P<rest>\S.*)$", re.IGNORECASE)
_FOLIO_SUFFIX_RE = re.compile(rf"^(?P<rest>.*\S)\s+{_FOLIO}\s*$", re.IGNORECASE)
_OPENING_NUMERAL_RE = re.compile(r"^\d+\s*")

if TYPE_CHECKING:
    from _extract.headband import RunningHeadBand


def folioless_shape(text: str) -> str:
    return " ".join(_DIGIT_RE.sub(" ", shape_of(text)).split())


class OpenedHeadings:
    def __init__(self) -> None:
        self._titles: list[str] = []
        self._match = HeadingMatch()
        self._printed_match = HeadingMatch.as_printed()

    def add(self, title: str, level: int) -> None:
        if level <= TOP_LEVEL:
            self._titles = []
        self._titles.append(title)

    def names(self, text: str) -> bool:
        return any(self._match.matches(text, title) for title in self._titles)

    def names_as_printed(self, text: str) -> bool:
        return any(self._printed_match.matches(text, title) for title in self._titles)


class RepeatedTitles:
    def __init__(self, opened: OpenedHeadings, work_title: str) -> None:
        self._opened = opened
        self._work_title = work_title

    @classmethod
    def none(cls) -> RepeatedTitles:
        return cls(OpenedHeadings(), "")

    def name(self, text: str) -> bool:
        return self._opened.names_as_printed(text) or self._names_the_work(text)

    def _names_the_work(self, text: str) -> bool:
        if not self._work_title or section_number_of(text) is not None:
            return False
        return HeadingMatch.as_printed().matches(text, self._work_title)


@dataclass(frozen=True)
class CandidatePlace:
    folio_beside: str | None = None
    inside_the_text: bool = False
    box: Box | None = None


@dataclass(frozen=True)
class HeadPrinting:
    text: str
    size: float | None
    place: CandidatePlace


@dataclass(frozen=True)
class FurnitureProfile:
    type_sizes: dict[str, float] = field(default_factory=dict)
    head_band: RunningHeadBand | None = None

    def with_head_band(self, head_band: RunningHeadBand | None) -> FurnitureProfile:
        return dataclasses.replace(self, head_band=head_band)

    def sets_in_display_type(self, text: str, size: float | None) -> bool:
        type_size = self._type_size_of(text)
        return size is not None and type_size is not None and size >= type_size * DISPLAY_TYPE_RATIO

    def sets_larger(self, text: str, size: float) -> bool:
        type_size = self._type_size_of(text)
        return type_size is not None and size > type_size + STYLE_SIZE_TOLERANCE_POINTS

    def holds_in_the_head_band(self, box: Box | None, size: float | None) -> bool:
        return self.head_band is not None and self.head_band.holds(box, size)

    def _type_size_of(self, text: str) -> float | None:
        return self.type_sizes.get(folioless_shape(text))


class _PrintedWords:
    def __init__(self, text: str) -> None:
        self._text = text
        self._prefixed = _FOLIO_PREFIX_RE.match(text)
        self._suffixed = _FOLIO_SUFFIX_RE.match(text)

    def readings(self) -> list[str]:
        return [self._text] + ([self._prefixed.group("rest")] if self._prefixed else [])

    def print_the_folio_at_either_end(self, folio: str | None) -> bool:
        ends = {printed.group("folio").lower() for printed in (self._prefixed, self._suffixed) if printed}
        return bool(folio) and folio.lower() in ends


class RunningHeads:
    def __init__(self, texts: list[str], profile: FurnitureProfile | None = None) -> None:
        self._texts = [text for text in texts if text.strip()]
        self._shapes = {shape_of(text) for text in self._texts if folioless_shape(text)}
        self._numbers = {_printed_form(text) for text in self._texts if not folioless_shape(text)}
        self._profile = profile or FurnitureProfile()

    def also(self, texts: list[str]) -> RunningHeads:
        return RunningHeads(self._texts + texts, self._profile)

    def names(self, text: str) -> bool:
        if folioless_shape(text):
            return shape_of(text) in self._shapes
        return _printed_form(text) in self._numbers

    def is_running_head(self, printing: HeadPrinting, titles: RepeatedTitles) -> bool:
        if printing.place.inside_the_text or self._profile.sets_in_display_type(printing.text, printing.size):
            return False
        in_the_band = self._profile.holds_in_the_head_band(printing.place.box, printing.size)
        return self._prints_the_words_of(printing, titles) or in_the_band

    def _prints_the_words_of(self, printing: HeadPrinting, titles: RepeatedTitles) -> bool:
        words = _PrintedWords(printing.text)
        if self.names(printing.text) or words.print_the_folio_at_either_end(printing.place.folio_beside):
            return True
        return any(titles.name(reading) for reading in words.readings())

    def repeats_past_its_opening_numeral(self, text: str) -> bool:
        shape = _past_the_opening_numeral(text)
        printings = sum(_past_the_opening_numeral(held) == shape for held in self._texts)
        return not shape or printings >= REPEATED_PAGES


def _printed_form(text: str) -> str:
    return "".join(text.split()).casefold()


def _past_the_opening_numeral(text: str) -> str:
    return _OPENING_NUMERAL_RE.sub("", shape_of(text), count=1)
