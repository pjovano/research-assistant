from __future__ import annotations

import unicodedata

from .spans import WordGrid


class FoldedWords:
    def __init__(self, grid: WordGrid) -> None:
        self._word_of_character: list[int] = []
        folded_words = []
        for box in grid.boxes:
            folded = FoldedWords.folded(box.text)
            folded_words.append(folded)
            self._word_of_character.extend([box.index] * len(folded))
        self._text = "".join(folded_words)

    @staticmethod
    def folded(text: str) -> str:
        return "".join(character for character in unicodedata.normalize("NFKD", text).lower() if character.isalnum())

    def spans_of(self, words: str) -> list[tuple[int, int]]:
        wanted = FoldedWords.folded(words)
        if not wanted:
            return []
        return [self._span(start, len(wanted)) for start in self._starts(wanted)]

    def _starts(self, wanted: str) -> list[int]:
        starts, position = [], self._text.find(wanted)
        while position >= 0:
            starts.append(position)
            position = self._text.find(wanted, position + 1)
        return starts

    def _span(self, start: int, length: int) -> tuple[int, int]:
        last_word = self._word_of_character[start + length - 1]
        return self._word_of_character[start], last_word + 1


class QuotationSpan:
    def __init__(self, grid: WordGrid, quotation: str) -> None:
        self._spans = FoldedWords(grid).spans_of(quotation)

    def located(self) -> tuple[int, int] | None:
        return self._spans[0] if len(self._spans) == 1 else None


class CrossPageQuotationSpan:
    def __init__(self, first: WordGrid, second: WordGrid, quotation: str) -> None:
        self._first = FoldedWords(first)
        self._second = FoldedWords(second)
        self._words = quotation.split()

    def located(self) -> tuple[int, int] | None:
        splits = [split for cut in range(1, len(self._words)) if (split := self._split_at(cut))]
        return splits[0] if len(splits) == 1 else None

    def _split_at(self, cut: int) -> tuple[int, int] | None:
        opening = self._first.spans_of(" ".join(self._words[:cut]))
        closing = self._second.spans_of(" ".join(self._words[cut:]))
        if len(opening) != 1 or len(closing) != 1:
            return None
        return opening[0][0], closing[0][1]
