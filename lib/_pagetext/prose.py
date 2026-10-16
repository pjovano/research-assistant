from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from confusables import canonical
from math_fonts import MathFonts
from notation import delimited_spans, is_symbol, without_notation


@dataclass(frozen=True)
class RemovedNotation:
    spans: tuple[str, ...]
    characters: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.spans and not self.characters

    def listed(self) -> list[str]:
        return list(self.spans) + list(self.characters)


class QuotedNotation:
    def __init__(self, pdf_path: Path, quote: str) -> None:
        self._fonts = MathFonts(pdf_path)
        self._quote = quote
        self._spans = tuple(delimited_spans(quote))
        self._characters = self._notation_characters(without_notation(quote))

    def removed(self) -> RemovedNotation:
        return RemovedNotation(self._spans, self._characters)

    def prose(self) -> str:
        stripped = without_notation(self._quote)
        return "".join(char for char in stripped if char not in self._characters)

    def prose_pages(self) -> list[tuple[int, str]]:
        return self._fonts.prose_texts()

    def _notation_characters(self, text: str) -> tuple[str, ...]:
        if not any(is_symbol(char) for char in text):
            return ()
        held = {canonical(char) for char in self._fonts.notation_characters()}
        return tuple(dict.fromkeys(char for char in text if canonical(char) in held))

