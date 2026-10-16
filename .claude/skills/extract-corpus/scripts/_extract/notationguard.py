from __future__ import annotations

import html
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from latex_symbols import MathMacros

from _extract.blocks import TAG_RE as _TAG_RE
from _extract.enginemath import MATH_ELEMENT_RE
from _extract.formulaalphabets import AlphabetConflict, AlphabetRepair
from _extract.formulasymbols import FormulaSymbols, FormulaUnit, folded_units

AGREED = "agreed"
CORRECTED = "corrected"
FLAGGED = "flagged"
MAX_SUBSTITUTION_KINDS = 2
COMPOSITE_MACROS = {"|∼": "\\mid\\!\\sim"}
LATIN_LIMIT = 0x0250
PLAIN_CATEGORIES = ("L", "N", "P", "S")
SYMBOL_KIND = "symbol"
PRIME_SHORTHAND = "'"
RAISED_TEMPLATE = "^{{{macro}}}"
_FORMULA_PLACE = "\x00"



@dataclass(frozen=True)
class NotationVerdict:
    status: str
    latex: str


class NotationGuard:
    def __init__(self) -> None:
        self._macros = MathMacros()

    def checked(self, latex: str, layer_text: str) -> NotationVerdict:
        verdict = self._symbols_checked(latex, layer_text)
        if verdict.status == FLAGGED:
            return verdict
        try:
            repaired = AlphabetRepair(verdict.latex, layer_text).repaired()
        except AlphabetConflict:
            return NotationVerdict(FLAGGED, latex)
        return self._with_alphabets(verdict, repaired)

    @staticmethod
    def _with_alphabets(verdict: NotationVerdict, repaired: str) -> NotationVerdict:
        return verdict if repaired == verdict.latex else NotationVerdict(CORRECTED, repaired)

    def _symbols_checked(self, latex: str, layer_text: str) -> NotationVerdict:
        comparison = _UnitComparison(FormulaSymbols(latex).units(), folded_units(layer_text))
        if comparison.agrees():
            return NotationVerdict(AGREED, latex)
        if not comparison.is_correctable():
            return NotationVerdict(FLAGGED, latex)
        return self._corrected(latex, comparison.substitutions())

    def _corrected(self, latex: str, substitutions: list[tuple[FormulaUnit, str]]) -> NotationVerdict:
        corrected = latex
        for unit, text in sorted(substitutions, key=lambda pair: pair[0].start, reverse=True):
            macro = COMPOSITE_MACROS.get(text) or self._macros.macro(text)
            if macro is None or not unit.replaceable:
                return NotationVerdict(FLAGGED, latex)
            written = self._in_place_of(latex[unit.start:unit.end], macro)
            corrected = corrected[:unit.start] + self._spaced(written, corrected[unit.end:]) + corrected[unit.end:]
        return NotationVerdict(CORRECTED, corrected)

    @staticmethod
    def _in_place_of(source: str, macro: str) -> str:
        return RAISED_TEMPLATE.format(macro=macro) if source == PRIME_SHORTHAND else macro

    @staticmethod
    def _spaced(macro: str, following: str) -> str:
        runs_into_a_letter = macro[-1:].isalpha() and macro.startswith("\\") and following[:1].isalpha()
        return macro + " " if runs_into_a_letter else macro


class _UnitComparison:
    def __init__(self, formula_units: list[FormulaUnit], layer_units: list[str]) -> None:
        self._formula_units = formula_units
        self._layer_units = layer_units
        formula_counts = Counter(unit.text for unit in formula_units)
        layer_counts = Counter(layer_units)
        self._misread = formula_counts - layer_counts
        self._unread = layer_counts - formula_counts

    def agrees(self) -> bool:
        return bool(self._layer_units) and not self._misread and not self._unread

    def is_correctable(self) -> bool:
        count = self._misread.total()
        balanced = count == self._unread.total()
        few = 0 < count <= max(1, len(self._layer_units) // 2)
        consistent = len(self._substitution_kinds()) <= MAX_SUBSTITUTION_KINDS
        return balanced and few and consistent and not self._trades_a_glyph_for_one_of_another_kind()

    def _trades_a_glyph_for_one_of_another_kind(self) -> bool:
        return any(_glyph_kind(text) not in (SYMBOL_KIND, _glyph_kind(unit.text)) for unit, text in self.substitutions())

    def substitutions(self) -> list[tuple[FormulaUnit, str]]:
        pairs = zip(self._differing_formula_units(), self._differing_layer_units())
        return [(unit, text) for unit, text in pairs if unit.text != text]

    def _substitution_kinds(self) -> set[tuple[str, str]]:
        return {(unit.text, text) for unit, text in self.substitutions()}

    def _differing_formula_units(self) -> list[FormulaUnit]:
        return [unit for unit in self._formula_units if unit.text in self._differing()]

    def _differing_layer_units(self) -> list[str]:
        return [text for text in self._layer_units if text in self._differing()]

    def _differing(self) -> set[str]:
        return set(self._misread) | set(self._unread)


class FormulaRegions:
    def __init__(self, html_text: str, layer_text: str) -> None:
        self._engine_text = _plain(MATH_ELEMENT_RE.sub(_FORMULA_PLACE, html_text))
        self._layer_text = _plain(layer_text)

    def regions(self) -> list[str]:
        regions = {}
        matcher = SequenceMatcher(None, self._engine_text, self._layer_text, autojunk=False)
        for _tag, engine_start, engine_end, layer_start, layer_end in matcher.get_opcodes():
            regions.update(self._places_in(engine_start, engine_end, self._layer_text[layer_start:layer_end]))
        return [regions.get(place, "") for place in self._places()]

    def _places_in(self, start: int, end: int, layer_span: str) -> dict[int, str]:
        places = [place for place in range(start, end) if self._engine_text[place] == _FORMULA_PLACE]
        prose = self._engine_text[start:end].replace(_FORMULA_PLACE, "").strip()
        holds_one_formula_alone = len(places) == 1 and not prose
        return {place: layer_span.strip() if holds_one_formula_alone else "" for place in places}

    def _places(self) -> list[int]:
        return [place for place, char in enumerate(self._engine_text) if char == _FORMULA_PLACE]


def _glyph_kind(text: str) -> str:
    if not _is_plain(text):
        return SYMBOL_KIND
    return "".join(sorted({unicodedata.category(char)[0] for char in text}))


def _is_plain(text: str) -> bool:
    return all(ord(char) < LATIN_LIMIT and unicodedata.category(char).startswith(PLAIN_CATEGORIES) for char in text)


def _plain(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text))
