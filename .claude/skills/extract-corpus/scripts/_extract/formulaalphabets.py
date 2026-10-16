from __future__ import annotations

import unicodedata

from _extract.alphabets import ALPHABET_COMMANDS, alphabet_of
from _extract.formulasymbols import FormulaSymbol, FormulaSymbols, folded

_LETTER_CATEGORY = "L"


class AlphabetConflict(Exception):
    pass


class AlphabetRepair:
    def __init__(self, latex: str, layer_text: str) -> None:
        self._latex = latex
        self._layer_alphabets = _LayerAlphabets(layer_text)

    def repaired(self) -> str:
        symbols = FormulaSymbols(self._latex).symbols()
        edits = {}
        for symbol in symbols:
            target = self._layer_alphabets.of(folded(symbol.char))
            if target is not None and _alphabet_of(symbol) != target:
                edits.update(self._edit(symbol, symbols, target))
        repaired = self._latex
        for (start, end), replacement in sorted(edits.items(), reverse=True):
            repaired = repaired[:start] + replacement + repaired[end:]
        return repaired

    def _edit(self, symbol: FormulaSymbol, symbols: list[FormulaSymbol], target: str) -> dict:
        command = ALPHABET_COMMANDS[target]
        if symbol.group is None and symbol.char.isascii():
            return {(symbol.start, symbol.end): f"{command}{{{symbol.char}}}"}
        if symbol.group is not None and [other.group for other in symbols].count(symbol.group) == 1:
            return {(symbol.group.command_start, symbol.group.command_end): command}
        raise AlphabetConflict(f"no single letter to set in {target} at {symbol.start} of {self._latex!r}")


class _LayerAlphabets:
    def __init__(self, layer_text: str) -> None:
        self._alphabets: dict[str, set[str | None]] = {}
        for char in unicodedata.normalize("NFC", layer_text):
            if unicodedata.category(char).startswith(_LETTER_CATEGORY):
                self._alphabets.setdefault(folded(char), set()).add(alphabet_of(char))

    def of(self, letter: str) -> str | None:
        alphabets = self._alphabets.get(letter, {None})
        if alphabets == {None}:
            return None
        if len(alphabets) > 1:
            raise AlphabetConflict(f"the text layer sets {letter!r} in {sorted(map(str, alphabets))}")
        return next(iter(alphabets))


def _alphabet_of(symbol: FormulaSymbol) -> str | None:
    return symbol.group.alphabet if symbol.group is not None else alphabet_of(symbol.char)
