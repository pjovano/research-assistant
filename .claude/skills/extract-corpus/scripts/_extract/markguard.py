from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from _extract.blocks import TAG_RE as _TAG_RE
from _extract.notemarks import RAISED_NUMBER_RE, raised_mark

_WORD_RE = re.compile(r"\w+")


@dataclass(frozen=True)
class _RaisedMark:
    start: int
    end: int
    number: str
    word_before: str

    @property
    def key(self) -> tuple[str, str]:
        return self.number, self.word_before


class MarkGuard:
    def __init__(self, layer_html: str) -> None:
        layer_marks = _raised_marks(layer_html)
        self._layer_counts = Counter(mark.number for mark in layer_marks)
        self._layer_keys = {mark.key for mark in layer_marks}
        self._layer_numbers_after: dict[str, list[str]] = {}
        for mark in layer_marks:
            self._layer_numbers_after.setdefault(mark.word_before, []).append(mark.number)

    def corrected(self, engine_html: str) -> str:
        marks = _raised_marks(engine_html)
        for mark in reversed(self._unprinted_twins(marks)):
            engine_html = engine_html[:mark.start] + engine_html[mark.end:]
        return self._renumbered(engine_html)

    def _unprinted_twins(self, marks: list[_RaisedMark]) -> list[_RaisedMark]:
        engine_counts = Counter(mark.number for mark in marks)
        confirmed = {mark.number for mark in marks if mark.key in self._layer_keys}
        overcounted = {number for number in confirmed if self._layer_counts[number] < engine_counts[number]}
        return [mark for mark in marks if mark.number in overcounted and mark.key not in self._layer_keys]

    def _renumbered(self, engine_html: str) -> str:
        marks = _raised_marks(engine_html)
        for mark in reversed(marks):
            printed = self._numeral_printed_instead(mark, marks)
            if printed is not None:
                engine_html = engine_html[:mark.start] + raised_mark(printed) + engine_html[mark.end:]
        return engine_html

    def _numeral_printed_instead(self, mark: _RaisedMark, marks: list[_RaisedMark]) -> str | None:
        printed = self._layer_numbers_after.get(mark.word_before, [])
        raised_after_the_word = [other for other in marks if other.word_before == mark.word_before]
        if mark.key in self._layer_keys or len(printed) != 1 or len(raised_after_the_word) != 1:
            return None
        return None if printed[0] in {other.number for other in marks} else printed[0]


def _raised_marks(html: str) -> list[_RaisedMark]:
    return [_RaisedMark(found.start(), found.end(), found.group(1), _last_word(html[:found.start()]))
            for found in RAISED_NUMBER_RE.finditer(html)]


def _last_word(html: str) -> str:
    words = _WORD_RE.findall(_TAG_RE.sub("", html))
    return words[-1].lower() if words else ""
