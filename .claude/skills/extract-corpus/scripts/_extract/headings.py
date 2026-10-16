from __future__ import annotations

import itertools
import re
import statistics
import unicodedata
from dataclasses import dataclass
from typing import Callable

from _pagetext.folio import ROMAN_NUMERAL_PATTERN
from notation import delimited_spans, display_latex_span, unwrapped_notation, without_notation

from _extract.blocks import Block
from _extract.elements import Heading
from _extract.layer import TextLayer
from _extract.layerhtml import LIGATURES
from _extract.outline import Heading as OutlineHeading

MAX_HEADING_LEVEL = 6
MIN_SHAPE_CHARS = 8
MIN_MISPRINTED_WORD_LETTERS = 6
OPENING_WORDS = 2
SIZE_STEP_POINTS = 0.5
MIN_KEY_OCCURRENCES = 2
RARE_STYLE_RANK = 0
ITALIC_SHARE = 0.4
BOLD_SHARE = 0.5
NO_KEY = (0.0, False, False)
_SHAPE_RE = re.compile(r"[^a-z0-9]+")
_LEADING_ENUMERATOR_RE = re.compile(r"^\s*(\d+(\.\d+)*|[ivxlcdm]+|(?-i:[A-Z](\.\d+)*(?=\.?\s+[A-Z])))\.?\s+",
                                    re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(r"^\s*\w+(\s+\w+){0,2}\s*:\s+(?=\S)")
WORD_GAP_RATIO = 0.4
MIN_SPACED_TOKENS = 6
SPACED_TOKEN_SHARE = 0.6
SMALL_CAPITALS_FONT_RE = re.compile(r"SC(?![a-z])|SCap|Caps")
SMALL_CAPITALS_SHARE = 0.5
SUBSET_PREFIX_END = "+"
UNSPACED_KIND = ""
LETTER_KIND = "letter"
DIGIT_KIND = "digit"
RUN_IN_LABEL_RE = re.compile(r"^\S+\s?:$")
_LABEL_WORDS = r"chapter|part|book|lecture|section|kapitel|teil|chapitre|partie"
BARE_LABEL_RE = re.compile(rf"^(?:{_LABEL_WORDS})\s+(?P<number>\S+)$", re.IGNORECASE)
_LEADING_BARE_LABEL_RE = re.compile(rf"^\s*(?:{_LABEL_WORDS})\s+\S+\s+(?=\S)", re.IGNORECASE)
_SUBTITLE_JOINT_RE = re.compile(r":\s+|\s+[—–]\s+")
_SENTENCE_END_RE = re.compile(r"[.!?][\"'”’)\]]*$")
_LETTERED_LABEL_RE = re.compile(r"^\s*\(?[a-z]\)\s+(?=\S)")
_DISPLAY_NUMBER_RE = re.compile(r"^\((?:\d+|[ivxlcdm]+|[a-z])\)\s+\S", re.IGNORECASE)
MIN_SENTENCE_WORDS = 2
_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
    "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
    "xi": "11", "xii": "12", "xiii": "13", "xiv": "14", "xv": "15", "xvi": "16", "xvii": "17", "xviii": "18",
    "xix": "19", "xx": "20", "thirty": "30", "forty": "40", "fifty": "50",
}
_TENS = {"20", "30", "40", "50", "60", "70", "80", "90"}
_UNIT_DIGITS = {str(unit) for unit in range(1, 10)}
_LETTER_PART = r"\.[a-z](?=\.)"
_NUMERAL_PARTS = r"(?:\.(?:[ivxlcdm]+|\d+))"
_SECTION_NUMBER_RE = re.compile(
    rf"^\s*(?:(?P<arabic>\d+(?:\s*\.\s*\d+)*(?:{_LETTER_PART})?)\s*\.?"
    rf"|(?P<dotted>[ivxlcdm]+{_NUMERAL_PARTS}*{_LETTER_PART}|[ivxlcdm]+{_NUMERAL_PARTS}+)\.?"
    r"|(?P<roman>[ivxlcdm]+)\s*\.)\s*(?=[^\W\d_])", re.IGNORECASE)
_NUMBER_JOINT = "."
_SPACES_RE = re.compile(r"\s+")
_ROMAN_ONE_READ_AS_A_DIGIT = str.maketrans("1", "i")
_BARE_ROMAN_NUMERAL_RE = re.compile(rf"^(?:{ROMAN_NUMERAL_PATTERN})\.?$", re.IGNORECASE)


def shape_of(text: str) -> str:
    words = [_NUMBER_WORDS.get(word, word) for word in _SHAPE_RE.sub(" ", _unaccented_lowercase(text)).split()]
    return " ".join(_compounded(words))


def _unaccented_lowercase(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def section_number_of(text: str) -> tuple[str, ...] | None:
    found = _SECTION_NUMBER_RE.match(text)
    if found is None:
        return None
    numerals = found.group("arabic") or found.group("dotted") or found.group("roman")
    return tuple(_value_of(numeral.strip()) for numeral in numerals.lower().split(_NUMBER_JOINT))


def is_a_bare_roman_numeral(text: str) -> bool:
    return _BARE_ROMAN_NUMERAL_RE.match(text.strip()) is not None


def past_enumerator(text: str) -> str:
    return _past_lettered_label(past_section_number(text))


def _past_lettered_label(text: str) -> str:
    found = _LETTERED_LABEL_RE.match(text)
    return text if found is None else text[found.end():]


def past_section_number(text: str) -> str:
    found = _SECTION_NUMBER_RE.match(text)
    if found is None or not all(part.isdigit() for part in section_number_of(text)):
        return text
    return text[found.end():]


def _numbered_alike(text: str, other: str) -> bool:
    return section_number_of(text) == section_number_of(other) or _numeral_glyphs(text) == _numeral_glyphs(other)


def _numbered_as(title: str, block_text: str) -> str:
    block_number = _SECTION_NUMBER_RE.match(block_text).group(0)
    return block_number + title[_SECTION_NUMBER_RE.match(title).end():]


def _numeral_glyphs(text: str) -> str:
    found = _SECTION_NUMBER_RE.match(text)
    numerals = found.group("arabic") or found.group("dotted") or found.group("roman")
    return _SPACES_RE.sub("", numerals).lower().translate(_ROMAN_ONE_READ_AS_A_DIGIT)


def _value_of(numeral: str) -> str:
    return str(int(numeral)) if numeral.isdigit() else _NUMBER_WORDS.get(numeral, numeral)


class _TitleSpelling:
    def __init__(self, text: str) -> None:
        self._letters = _SHAPE_RE.sub("", _unaccented_lowercase(text))
        self._words = shape_of(text).split()

    def is_empty(self) -> bool:
        return not self._words

    def is_alike(self, wanted: _TitleSpelling) -> bool:
        return self._spelt_as(wanted) or self._misreads_one_letter_of(wanted) or self._shares_an_opening_with(wanted)

    def _spelt_as(self, wanted: _TitleSpelling) -> bool:
        return self._letters == wanted._letters or "".join(self._numbered_as(wanted)) == "".join(wanted._words)

    def _numbered_as(self, wanted: _TitleSpelling) -> list[str]:
        return [word for word in self._words if not word.isdigit() or word in wanted._words]

    def _misreads_one_letter_of(self, wanted: _TitleSpelling) -> bool:
        if len(self._words) != len(wanted._words):
            return False
        differing = [pair for pair in zip(self._words, wanted._words) if pair[0] != pair[1]]
        return len(differing) == 1 and _drops_an_inner_letter(*sorted(differing[0], key=len))

    def _shares_an_opening_with(self, wanted: _TitleSpelling) -> bool:
        printed, title = " ".join(self._words), " ".join(wanted._words)
        shorter = min(printed, title, key=len)
        return len(shorter) >= MIN_SHAPE_CHARS and (printed.startswith(title) or title.startswith(printed))


def _drops_an_inner_letter(shorter: str, longer: str) -> bool:
    if not longer.isalpha() or len(longer) < MIN_MISPRINTED_WORD_LETTERS or len(longer) != len(shorter) + 1:
        return False
    return any(longer[:index] + longer[index + 1:] == shorter for index in range(1, len(longer) - 1))


def _compounded(words: list[str]) -> list[str]:
    joined: list[str] = []
    for word in words:
        if joined and joined[-1] in _TENS and word in _UNIT_DIGITS:
            joined[-1] = str(int(joined[-1]) + int(word))
        else:
            joined.append(word)
    return joined


def _open_alike(numbered: str, other: str) -> bool:
    openings = [_opening_words(text) for text in (numbered, other)]
    return len(openings[0]) == OPENING_WORDS and openings[0] == openings[1]


def _opening_words(numbered: str) -> list[str]:
    return shape_of(_SECTION_NUMBER_RE.sub("", numbered, count=1)).split()[:OPENING_WORDS]


def _readings_of(text: str) -> tuple[str, ...]:
    patterns = (_LEADING_ENUMERATOR_RE, _LEADING_BARE_LABEL_RE, _LEADING_LABEL_RE)
    stripped = (pattern.sub("", text, count=1) for pattern in patterns)
    return tuple(dict.fromkeys([text, *stripped]))


def _notation_readings(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys([without_notation(text), unwrapped_notation(text)]))


def _as_printed(text: str) -> tuple[str, ...]:
    return (text,)


class HeadingMatch:
    def __init__(self, block_readings: Callable[[str], tuple[str, ...]] = _readings_of) -> None:
        self._block_readings = block_readings

    @classmethod
    def as_printed(cls) -> HeadingMatch:
        return cls(_as_printed)

    def matches(self, block_text: str, title: str) -> bool:
        wanted = without_notation(title)
        return any(self._words_match(reading, wanted) for reading in _notation_readings(block_text))

    def _words_match(self, block_text: str, title: str) -> bool:
        numbers = (section_number_of(block_text), section_number_of(title))
        if None in numbers:
            return self._worded_alike(block_text, title)
        if _numbered_alike(block_text, title):
            return _open_alike(block_text, title) or self._worded_alike(block_text, _numbered_as(title, block_text))
        return self._matches_past_the_titles_number(block_text, title)

    def _matches_past_the_titles_number(self, block_text: str, title: str) -> bool:
        inner = _LEADING_ENUMERATOR_RE.sub("", title, count=1)
        numbered_again = inner != title and section_number_of(inner) is not None
        return numbered_again and self._words_match(block_text, inner)

    def _worded_alike(self, block_text: str, title: str) -> bool:
        return any(self._alike(reading, wanted)
                   for reading in self._block_readings(block_text)
                   for wanted in _readings_of(title))

    @staticmethod
    def _alike(block_text: str, title: str) -> bool:
        printed, wanted = _TitleSpelling(block_text), _TitleSpelling(title)
        return not (printed.is_empty() or wanted.is_empty()) and printed.is_alike(wanted)


def holds_only_notation(text: str) -> bool:
    return bool(delimited_spans(text)) and not any(char.isalnum() for char in without_notation(text))


def displayed_notation(text: str) -> str:
    return display_latex_span(unwrapped_notation(text))


def reads_as_body_text(text: str) -> bool:
    return _reads_as_a_sentence(text) or _DISPLAY_NUMBER_RE.match(text.strip()) is not None


def _reads_as_a_sentence(text: str) -> bool:
    return ends_as_a_sentence(text) and not _is_numbered(text.strip())


def ends_as_a_sentence(text: str) -> bool:
    stripped = text.strip()
    return _SENTENCE_END_RE.search(stripped) is not None and len(stripped.split()) >= MIN_SENTENCE_WORDS


def _is_numbered(text: str) -> bool:
    return BARE_LABEL_RE.match(text) is not None or section_number_of(text) is not None


def label_printed_before(text: str, title: str) -> str | None:
    label = _LEADING_BARE_LABEL_RE.match(text)
    if label is None or _carries_a_label(title, label.group(0).strip()):
        return None
    return label.group(0).strip()


def _carries_a_label(title: str, label: str) -> bool:
    number = _value_of(BARE_LABEL_RE.match(label).group("number").lower())
    return _LEADING_BARE_LABEL_RE.match(title) is not None or section_number_of(title) == (number,)


def prints_the_opening_of(text: str, title: str) -> bool:
    printed = shape_of(text).split()
    return bool(printed) and any(shape_of(reading).split()[:len(printed)] == printed for reading in _readings_of(title))


class TitleParts:
    def __init__(self, title: str) -> None:
        parts = [shape_of(part) for part in _parts_of(title)]
        self._shapes = set(parts) - {""} if len(parts) > 1 else set()

    def names_one(self, text: str) -> bool:
        return any(shape_of(reading) in self._shapes for reading in _part_readings(text))


def _parts_of(title: str) -> list[str]:
    opening = _LEADING_BARE_LABEL_RE.match(title) or _LEADING_ENUMERATOR_RE.match(title)
    leading = [opening.group(0)] if opening else []
    rest = title[opening.end():] if opening else title
    return leading + _SUBTITLE_JOINT_RE.split(rest, maxsplit=1)


def _part_readings(text: str) -> list[str]:
    label = BARE_LABEL_RE.match(text.strip())
    return [text, label.group("number")] if label else [text]


class OutlineQueue:
    def __init__(self, headings: list[OutlineHeading]) -> None:
        self._pending = sorted(headings, key=lambda heading: heading.file_page)
        self._level = 0
        self._has_outline = bool(headings)

    def due_on(self, file_page: int) -> list[OutlineHeading]:
        return [heading for heading in self._pending if heading.file_page <= file_page]

    def release(self, file_page: int) -> None:
        due = self.due_on(file_page)
        self._pending = self._pending[len(due):]
        if due:
            self._level = due[-1].level

    @property
    def sublevel(self) -> int | None:
        if self._level == 0 and self._has_outline:
            return None
        return min(self._level + 1, MAX_HEADING_LEVEL)


@dataclass(frozen=True)
class HeadingText:
    text: str
    letter_spaced: bool
    marks: tuple[str, ...] = ()
    small_capitals: bool = False

    @property
    def is_display_lettering(self) -> bool:
        return self.letter_spaced or self.small_capitals


class SmallCapitalFont:
    def __init__(self, chars: list) -> None:
        self._chars = [char for char in chars if not char.is_blank]

    def sets(self) -> bool:
        in_small_capitals = sum(1 for char in self._chars if _names_small_capitals(char.font))
        return bool(self._chars) and in_small_capitals > SMALL_CAPITALS_SHARE * len(self._chars)


def _names_small_capitals(font: str) -> bool:
    return SMALL_CAPITALS_FONT_RE.search(font.rpartition(SUBSET_PREFIX_END)[2]) is not None


class LetterSpacedHeading:
    def __init__(self, chars: list) -> None:
        self._chars = [char for char in chars if not char.is_blank]

    def reading(self, text: str) -> HeadingText:
        if not self._reads_as_letter_spaced(text):
            return HeadingText(text, False)
        rejoined = "".join(self._rejoined_by_gaps()) if self._chars else _rejoined_by_kind(text)
        return HeadingText(rejoined.strip(), True)

    def rejoined(self, text: str) -> str:
        return self.reading(text).text

    def _rejoined_by_gaps(self):
        previous = None
        for char in self._chars:
            if previous is not None and self._breaks_a_word(previous, char):
                yield " "
            yield LIGATURES.get(char.char, char.char)
            previous = char

    def _breaks_a_word(self, previous, char) -> bool:
        return char.bbox.left - previous.bbox.right > WORD_GAP_RATIO * char.size

    @staticmethod
    def _reads_as_letter_spaced(text: str) -> bool:
        tokens = text.split()
        if len(tokens) < MIN_SPACED_TOKENS:
            return False
        return sum(len(token) == 1 for token in tokens) >= SPACED_TOKEN_SHARE * len(tokens)


def _rejoined_by_kind(text: str) -> str:
    runs = itertools.groupby(text.split(), key=_spaced_kind)
    return " ".join("".join(tokens) if kind else " ".join(tokens) for kind, tokens in runs)


def _spaced_kind(token: str) -> str:
    if len(token) != 1:
        return UNSPACED_KIND
    return LETTER_KIND if token.isalpha() else DIGIT_KIND if token.isdigit() else token


def rounded_size(size: float) -> float:
    return round(size / SIZE_STEP_POINTS) * SIZE_STEP_POINTS


class HeadingKey:
    def __init__(self, layer: TextLayer) -> None:
        self._layer = layer

    def of(self, block: Block) -> tuple[float, bool, bool]:
        chars = [char for char in self._layer.chars_in(block.file_page, block.bbox) if not char.char.isspace()]
        if not chars:
            return NO_KEY
        size = rounded_size(statistics.median(char.size for char in chars))
        bold = sum(char.bold for char in chars) > BOLD_SHARE * len(chars)
        italic = sum(char.italic for char in chars) >= ITALIC_SHARE * len(chars)
        return (size, bold, italic)


class HeadingLevels:
    def levelled(self, elements: list) -> list:
        ranks = self._ranks([element.key for element in elements if isinstance(element, Heading) and element.key])
        return [self._levelled(element, ranks) for element in elements]

    def _ranks(self, keys: list[tuple]) -> dict[tuple, int]:
        first_seen, counts = {}, {}
        for position, key in enumerate(keys):
            first_seen.setdefault(key, position)
            counts[key] = counts.get(key, 0) + 1
        frequent = sorted((key for key in first_seen if counts[key] >= MIN_KEY_OCCURRENCES),
                          key=lambda key: (-key[0], first_seen[key]))
        ranks = {key: rank for rank, key in enumerate(frequent)}
        return {key: ranks.get(key, RARE_STYLE_RANK) for key in first_seen}

    def _levelled(self, element, ranks: dict) -> object:
        if not isinstance(element, Heading) or element.key is None:
            return element
        return element.at_level(min(element.level + ranks[element.key], MAX_HEADING_LEVEL))
