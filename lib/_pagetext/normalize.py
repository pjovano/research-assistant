from __future__ import annotations

import re
import unicodedata
from typing import Callable

_QUOTE_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "‒": "-", "−": "-",
    " ": " ", "…": "...",
}

_DEHYPHEN_RE = re.compile(r"[-­][ \t]*\r?\n[ \t]*")
_WORD_HYPHEN_RE = re.compile(r"(?<=\w)-(?=\w)")
_WS_RE = re.compile(r"\s+")
_INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")
_SPACE_BEFORE_PUNCT_RE = re.compile(r" +([,.;:!?])")
_ESCAPED_PUNCTUATION_RE = re.compile(r"\\([\[\]|])")

_Aligned = list[tuple[str, int]]
_Survivor = Callable[[re.Match], tuple[str, int]]


def normalize(text: str) -> str:
    return NormalizedText(text).text


def typographic_form(text: str) -> str:
    return _WS_RE.sub(" ", _folded_characters(text)).strip()


def _folded_characters(text: str) -> str:
    return "".join(_QUOTE_MAP.get(piece, piece) for piece in unicodedata.normalize("NFKC", text))


def page_wording(raw: str) -> str:
    return _WS_RE.sub(" ", _DEHYPHEN_RE.sub("", raw)).strip()


class NormalizedText:
    def __init__(self, raw: str) -> None:
        self._raw = raw
        aligned = _CharacterPass().applied(raw)
        for regex_pass in _REGEX_PASSES:
            aligned = regex_pass.applied(aligned)
        aligned = _lowered(_stripped(aligned))
        self._text = "".join(char for char, _ in aligned)
        self._origins = [origin for _, origin in aligned]

    @property
    def text(self) -> str:
        return self._text

    def raw_span(self, start: int, length: int) -> tuple[int, int]:
        last = min(start + length, len(self._origins)) - 1
        if length <= 0 or last < start:
            return 0, 0
        return self._origins[start], self._end_after_marks(self._origins[last] + 1)

    def _end_after_marks(self, end: int) -> int:
        while end < len(self._raw) and unicodedata.combining(self._raw[end]):
            end += 1
        return end

    def page_text(self, start: int, length: int) -> str:
        first, end = self.raw_span(start, length)
        return page_wording(self._raw[first:end])


class _CharacterPass:
    def applied(self, raw: str) -> _Aligned:
        aligned: _Aligned = []
        for origin, char in enumerate(raw):
            if unicodedata.combining(char) and aligned:
                self._compose(aligned, char)
            else:
                aligned.extend((piece, origin) for piece in self._pieces(char))
        return aligned

    def _compose(self, aligned: _Aligned, mark: str) -> None:
        base, origin = aligned.pop()
        aligned.extend((piece, origin) for piece in self._pieces(base + mark))

    @staticmethod
    def _pieces(text: str) -> str:
        return _folded_characters(text)


class _RegexPass:
    def __init__(self, pattern: re.Pattern, survivor: _Survivor) -> None:
        self._pattern = pattern
        self._survivor = survivor

    def applied(self, aligned: _Aligned) -> _Aligned:
        text = "".join(char for char, _ in aligned)
        kept: _Aligned = []
        position = 0
        for match in self._pattern.finditer(text):
            kept.extend(aligned[position:match.start()])
            kept.extend(self._surviving(aligned, match))
            position = match.end()
        kept.extend(aligned[position:])
        return kept

    def _surviving(self, aligned: _Aligned, match: re.Match) -> _Aligned:
        replacement, offset = self._survivor(match)
        origin = aligned[match.start() + offset][1]
        return [(char, origin) for char in replacement]


def _deleted(_match: re.Match) -> tuple[str, int]:
    return "", 0


def _one_space(_match: re.Match) -> tuple[str, int]:
    return " ", 0


def _first_group(match: re.Match) -> tuple[str, int]:
    return match.group(1), match.start(1) - match.start()


_REGEX_PASSES = (
    _RegexPass(_ESCAPED_PUNCTUATION_RE, _first_group),
    _RegexPass(_DEHYPHEN_RE, _deleted),
    _RegexPass(_INVISIBLE_RE, _deleted),
    _RegexPass(_WORD_HYPHEN_RE, _deleted),
    _RegexPass(_WS_RE, _one_space),
    _RegexPass(_SPACE_BEFORE_PUNCT_RE, _first_group),
)


def _stripped(aligned: _Aligned) -> _Aligned:
    first = next((index for index, (char, _) in enumerate(aligned) if not char.isspace()), len(aligned))
    last = next((index for index in range(len(aligned) - 1, -1, -1) if not aligned[index][0].isspace()), -1)
    return aligned[first:last + 1]


def _lowered(aligned: _Aligned) -> _Aligned:
    text = "".join(char for char, _ in aligned)
    lowered = text.lower()
    if len(lowered) == len(text):
        return [(char, origin) for char, (_, origin) in zip(lowered, aligned)]
    return [(piece, origin) for char, origin in aligned for piece in char.lower()]
