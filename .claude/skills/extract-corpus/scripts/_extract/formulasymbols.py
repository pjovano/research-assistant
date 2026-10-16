from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from confusables import canonical
from latex_symbols import SUPPLEMENTARY_MACROS
from pylatexenc.latex2text import LatexNodes2Text
from pylatexenc.latexwalker import get_default_latex_context_db

from _extract.alphabets import COMMAND_ALPHABETS
from _extract.latexgroups import closing_of

_MACRO_RE = re.compile(r"\\([A-Za-z]+)")
_GROUP_NAME_RE = re.compile(r"\s*\{[^{}]*\}")
_ENVIRONMENT_MACROS = ("begin", "end")
_SIZED_DELIMITER_RE = re.compile(r"(?:left|right|middle|[bB]igg?[lrm]?)$")
_DELIMITER_RE = re.compile(r"\s*(?:\\[A-Za-z]+|\\.|.)")
_SPACING_ESCAPES = ",;:! \\"
_STRUCTURAL_CHARACTERS = "{}^_&~"
_WHITESPACE_CATEGORIES = ("Zs", "Zl", "Zp", "Cc", "Cf")
_LAYOUT_BRACES = "{}"
_ESCAPED_CHAR_LENGTH = len("\\x")
_BAR_FORMS = {"∣": "|"}
COMPOSITE_UNITS = {("|", "∼"): "|∼", ("|", "="): "⊨"}
EXTENSIBLE_ARROWS = {"xrightarrow": "→", "xleftarrow": "←"}
_OPTIONAL_ARGUMENT_OPENING_RE = re.compile(r"\s*\[")

_ARROW_SHAFT_RE = re.compile(r"-+(?=→)|(?<=←)-+")


@dataclass(frozen=True)
class FontGroup:
    command_start: int
    command_end: int
    argument_end: int
    alphabet: str

    def holds(self, position: int) -> bool:
        return self.command_end <= position < self.argument_end


@dataclass(frozen=True)
class FormulaSymbol:
    start: int
    end: int
    char: str
    group: FontGroup | None = None


@dataclass(frozen=True)
class FormulaUnit:
    start: int
    end: int
    text: str
    replaceable: bool

    def joined(self, following: FormulaUnit, text: str) -> FormulaUnit:
        return FormulaUnit(self.start, following.end, text, self.replaceable and following.replaceable)


class FormulaSymbols:
    def __init__(self, latex: str) -> None:
        self._latex = latex
        self._groups: list[FontGroup] = []
        self._layout_positions: set[int] = set()

    def text(self) -> str:
        return "".join(symbol.char for symbol in self.symbols())

    def units(self) -> list[FormulaUnit]:
        units = []
        for symbol in self.symbols():
            chars = unit_chars(symbol.char)
            units += [FormulaUnit(symbol.start, symbol.end, char, len(chars) == 1) for char in chars]
        return _Composites().joined(units, lambda unit: unit.text, FormulaUnit.joined)

    def symbols(self) -> list[FormulaSymbol]:
        self._groups = []
        self._layout_positions = set()
        symbols = []
        position = 0
        while position < len(self._latex):
            symbol, position = self._next(position)
            if symbol is not None:
                symbols.append(symbol)
        return symbols

    def _next(self, position: int) -> tuple[FormulaSymbol | None, int]:
        char = self._latex[position]
        if char == "\\":
            return self._escape(position)
        if char.isspace() or char in _STRUCTURAL_CHARACTERS or position in self._layout_positions:
            return None, position + 1
        return self._symbol(position, position + 1, char), position + 1

    def _symbol(self, start: int, end: int, char: str) -> FormulaSymbol:
        holding = [group for group in self._groups if group.holds(start)]
        return FormulaSymbol(start, end, char, holding[-1] if holding else None)

    def _escape(self, position: int) -> tuple[FormulaSymbol | None, int]:
        macro = _MACRO_RE.match(self._latex, position)
        if macro is not None:
            return self._macro(macro)
        escaped_end = position + _ESCAPED_CHAR_LENGTH
        escaped = self._latex[position + 1:escaped_end]
        if not escaped or escaped in _SPACING_ESCAPES:
            return None, escaped_end
        return self._symbol(position, escaped_end, escaped), escaped_end

    def _macro(self, macro: re.Match) -> tuple[FormulaSymbol | None, int]:
        if macro.group(1) in _ENVIRONMENT_MACROS:
            return None, self._after_environment_name(macro.end())
        if _SIZED_DELIMITER_RE.match(macro.group(1)):
            return None, self._after_delimiter(macro.end())
        if macro.group(1) in COMMAND_ALPHABETS:
            self._groups.append(FontGroup(macro.start(), macro.end(), self._argument_end(macro.end()),
                                          COMMAND_ALPHABETS[macro.group(1)]))
            return None, macro.end()
        if macro.group(1) in EXTENSIBLE_ARROWS:
            self._layout_positions.update(self._optional_argument_brackets(macro.end()))
            return self._symbol(macro.start(), macro.end(), EXTENSIBLE_ARROWS[macro.group(1)]), macro.end()
        char = macro_symbol(macro.group(0))
        if not char:
            return None, macro.end()
        return self._symbol(macro.start(), macro.end(), char), macro.end()

    def _argument_end(self, position: int) -> int:
        argument = _DELIMITER_RE.match(self._latex, position)
        if argument is None or not argument.group(0).endswith("{"):
            return position if argument is None else argument.end()
        closing = closing_of(self._latex, argument.end() - 1)
        return len(self._latex) if closing is None else closing + 1

    def _optional_argument_brackets(self, position: int) -> tuple[int, ...]:
        opening = _OPTIONAL_ARGUMENT_OPENING_RE.match(self._latex, position)
        if opening is None:
            return ()
        closing = closing_of(self._latex, opening.end() - 1)
        return () if closing is None else (opening.end() - 1, closing)

    def _after_delimiter(self, position: int) -> int:
        delimiter = _DELIMITER_RE.match(self._latex, position)
        return position if delimiter is None else delimiter.end()

    def _after_environment_name(self, position: int) -> int:
        name = _GROUP_NAME_RE.match(self._latex, position)
        return position if name is None else name.end()


@lru_cache(maxsize=None)
def macro_symbol(macro: str) -> str:
    if macro in SUPPLEMENTARY_MACROS:
        return SUPPLEMENTARY_MACROS[macro]
    if _takes_arguments(macro):
        return ""
    return LatexNodes2Text().latex_to_text(macro).strip()


def _takes_arguments(macro: str) -> bool:
    spec = get_default_latex_context_db().get_macro_spec(macro.lstrip("\\"))
    return spec is not None and bool(spec.args_parser.argspec)


def folded(text: str) -> str:
    composed = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", text))
    return "".join(canonical(char) for char in composed if unicodedata.category(char) not in _WHITESPACE_CATEGORIES)


def unit_chars(text: str) -> list[str]:
    return [_BAR_FORMS.get(char, char) for char in folded(text) if char not in _LAYOUT_BRACES]


def folded_units(text: str) -> list[str]:
    chars = list(_ARROW_SHAFT_RE.sub("", "".join(unit_chars(text))))
    return _Composites().joined(chars, lambda char: char, lambda first, _second, joined: joined)


class _Composites:
    def joined(self, units: list, text_of, join) -> list:
        joined = []
        for unit in units:
            composite = COMPOSITE_UNITS.get((text_of(joined[-1]), text_of(unit))) if joined else None
            if composite is None:
                joined.append(unit)
            else:
                joined[-1] = join(joined[-1], unit, composite)
        return joined
