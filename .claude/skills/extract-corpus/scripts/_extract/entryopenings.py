from __future__ import annotations

import difflib
import re
from typing import Callable

from _extract.sentences import closes_a_sentence

_UNCOMPARED_RE = re.compile(r"\W")
_LINE_BREAK = "\n"

OpeningGuard = Callable[[list[str], int], bool]


def closes_a_sentence_before(words: list[str], index: int) -> bool:
    return index > 0 and closes_a_sentence(words[index - 1])


def follows_a_word(_words: list[str], index: int) -> bool:
    return index > 0


class LayerEntryOpenings:
    def __init__(self, layer_entries: list[str], may_open: OpeningGuard = closes_a_sentence_before) -> None:
        self._may_open = may_open
        self._words: list[str] = []
        self._openings: set[int] = set()
        for entry in layer_entries:
            self._openings.add(len(self._words))
            self._words.extend(_comparable(word) for word in entry.split())

    def entries(self, text: str) -> list[str]:
        lines = [line.split() for line in text.split(_LINE_BREAK)]
        words = [word for line in lines for word in line]
        breaks = _line_starts(lines) | self._entry_openings_in(words)
        return [" ".join(words[start:end]) for start, end in _spans(sorted(breaks), len(words))]

    def _entry_openings_in(self, words: list[str]) -> set[int]:
        matcher = difflib.SequenceMatcher(None, self._words, [_comparable(word) for word in words], autojunk=False)
        aligned = {engine + offset: layer + offset for layer, engine, size in matcher.get_matching_blocks()
                   for offset in range(size)}
        return {index for index, layer_index in aligned.items()
                if layer_index in self._openings and self._may_open(words, index)}


def _comparable(word: str) -> str:
    return _UNCOMPARED_RE.sub("", word.lower())


def _line_starts(lines: list[list[str]]) -> set[int]:
    starts, count = set(), 0
    for line in lines:
        starts.add(count)
        count += len(line)
    return starts


def _spans(starts: list[int], word_count: int) -> list[tuple[int, int]]:
    return list(zip(starts, starts[1:] + [word_count]))
