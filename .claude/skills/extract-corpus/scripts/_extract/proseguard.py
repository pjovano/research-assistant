from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Callable

from _extract.blocks import TAG_RE as _TAG_RE
from _extract.enginemath import MATH_ELEMENT_RE

REPLACED = "replace"
LETTERS_PER_SLIP = 4
PAIR = 2
HYPHEN = "-"
CURLY_FORMS = {"'": frozenset("‘’"), '"': frozenset("“”")}
QUOTE_MARKS = frozenset("'\"‘’“”")
_SLASHED_NUMERAL = r"/\d+"
_SLASHED_NUMERAL_RE = re.compile(_SLASHED_NUMERAL)
_WORD_RE = re.compile(rf"[^\W\d_]+(?:{_SLASHED_NUMERAL})?")
_WORD_OR_QUOTE_RE = re.compile(r"[^\W\d_]+|['\"‘’“”]")
_WORD_OR_NUMERAL_RE = re.compile(r"[^\W_]+(?:\.[^\W_]+)*")
_NUMERAL_RE = re.compile(r"\d+(?:\.\d+)*")
DIGITS_READ_AS_LETTERS = {"I": "1", "l": "1", "O": "0", "o": "0"}
_ITALIC_TAG = r"</?(?:i|em)>"
_ITALIC_TAG_RE = re.compile(_ITALIC_TAG)
_TOKEN_ACROSS_ITALICS_RE = re.compile(rf"[^\W_]+(?:(?:{_ITALIC_TAG})+[^\W_]+)*")
_PREFIXED_DIGITS_RE = re.compile(r"(?P<prefix>[^\W\d_]*)(?P<digits>\d+)")
_DIGIT_RE = re.compile(r"\d")
_LETTER_RE = re.compile(r"[^\W\d_]")
CLOSING_TAG_OPENER = "</"


TakesTheLayersForm = Callable[[str, str], bool]
StretchPairing = Callable[[list[str], "_LayerWords", int, int], list[tuple[int, str]]]


class ProseGuard:
    def corrected(self, engine_html: str, layer_html: str) -> str:
        spelled = _LayerReading(_WORD_RE, _read_as_text(_is_a_slip),
                                _in_step_or_as_a_compound).corrected(engine_html, layer_html)
        numbered = _LayerReading(_WORD_OR_NUMERAL_RE, _read_as_text(_reads_a_numeral_as_letters)).corrected(
            spelled, layer_html)
        return _LayerReading(_WORD_OR_QUOTE_RE, _read_as_text(_takes_the_curly_form),
                             _quotes_in_order).corrected(numbered, layer_html)


class NumeralGuard:
    def corrected(self, engine_html: str, layer_html: str) -> str:
        return _LayerReading(_TOKEN_ACROSS_ITALICS_RE, _takes_the_layers_digits).corrected(engine_html, layer_html)


class _LayerWords:
    def __init__(self, layer_html: str, tokens: re.Pattern) -> None:
        self._text = _TAG_RE.sub(" ", layer_html)
        self._matches = list(tokens.finditer(self._text))
        self.tokens = [match.group(0) for match in self._matches]

    def compound(self, start: int, end: int) -> str | None:
        held = self._matches[start:end]
        separators = [self._text[before.end():after.start()] for before, after in zip(held, held[1:])]
        return self._text[held[0].start():held[-1].end()] if all(gap == HYPHEN for gap in separators) else None


def _in_step(engine_stretch: list[str], layer: _LayerWords, layer_start: int, layer_end: int) -> list[tuple[int, str]]:
    if len(engine_stretch) != layer_end - layer_start:
        return []
    return list(enumerate(layer.tokens[layer_start:layer_end]))


def _in_step_or_as_a_compound(engine_stretch: list[str], layer: _LayerWords, layer_start: int,
                              layer_end: int) -> list[tuple[int, str]]:
    compound = layer.compound(layer_start, layer_end) if len(engine_stretch) == 1 else None
    return [(0, compound)] if compound is not None else _in_step(engine_stretch, layer, layer_start, layer_end)


def _quotes_in_order(engine_stretch: list[str], layer: _LayerWords, layer_start: int,
                     layer_end: int) -> list[tuple[int, str]]:
    engine_quotes = [offset for offset, token in enumerate(engine_stretch) if token in QUOTE_MARKS]
    layer_quotes = [token for token in layer.tokens[layer_start:layer_end] if token in QUOTE_MARKS]
    return list(zip(engine_quotes, layer_quotes)) if len(engine_quotes) == len(layer_quotes) else []


class _LayerReading:
    def __init__(self, tokens: re.Pattern, takes_the_layers_form: TakesTheLayersForm,
                 paired: StretchPairing = _in_step) -> None:
        self._tokens = tokens
        self._takes_the_layers_form = takes_the_layers_form
        self._paired = paired

    def corrected(self, engine_html: str, layer_html: str) -> str:
        engine_tokens = _ProseTokens(engine_html, self._tokens).spans()
        layer = _LayerWords(layer_html, self._tokens)
        token_htmls = [engine_html[start:end] for _text, (start, end) in engine_tokens]
        replacements = self._replacements([text for text, _span in engine_tokens], token_htmls, layer)
        corrected = engine_html
        for index in sorted(replacements, reverse=True):
            start, end = engine_tokens[index][1]
            corrected = corrected[:start] + _with_unpaired_tags(replacements[index], corrected[start:end]) + corrected[end:]
        return corrected

    def _replacements(self, engine: list[str], token_htmls: list[str], layer: _LayerWords) -> dict[int, str]:
        replacements: dict[int, str] = {}
        matcher = SequenceMatcher(None, engine, layer.tokens, autojunk=False)
        for tag, engine_start, engine_end, layer_start, layer_end in matcher.get_opcodes():
            if tag != REPLACED:
                continue
            pairs = self._paired(engine[engine_start:engine_end], layer, layer_start, layer_end)
            replacements.update({engine_start + offset: form for offset, form in pairs
                                 if self._takes_the_layers_form(token_htmls[engine_start + offset], form)})
        return replacements


class _ProseTokens:
    def __init__(self, engine_html: str, tokens: re.Pattern) -> None:
        self._html = engine_html
        self._tokens = tokens

    def spans(self) -> list[tuple[str, tuple[int, int]]]:
        hidden = self._hidden_ranges()
        return [(_TAG_RE.sub("", match.group(0)), match.span()) for match in self._tokens.finditer(self._html)
                if not any(start <= match.start() < end for start, end in hidden)]

    def _hidden_ranges(self) -> list[tuple[int, int]]:
        return [match.span() for pattern in (MATH_ELEMENT_RE, _TAG_RE) for match in pattern.finditer(self._html)]


def _read_as_text(takes_the_layers_form: TakesTheLayersForm) -> TakesTheLayersForm:
    return lambda token_html, layer_token: takes_the_layers_form(_TAG_RE.sub("", token_html), layer_token)


def _reads_a_numeral_as_letters(engine_token: str, layer_token: str) -> bool:
    if not _NUMERAL_RE.fullmatch(layer_token) or len(engine_token) != len(layer_token) or engine_token == layer_token:
        return False
    return all(DIGITS_READ_AS_LETTERS.get(read, read) == printed for read, printed in zip(engine_token, layer_token))


def _with_unpaired_tags(replacement: str, replaced_html: str) -> str:
    unclosed: list[str] = []
    unopened: list[str] = []
    for tag in _TAG_RE.findall(replaced_html):
        if not tag.startswith(CLOSING_TAG_OPENER):
            unclosed.append(tag)
        elif unclosed:
            unclosed.pop()
        else:
            unopened.append(tag)
    return "".join(unopened) + replacement + "".join(unclosed)


def _takes_the_layers_digits(token_html: str, layer_token: str) -> bool:
    engine_token = _TAG_RE.sub("", token_html)
    printed = _PREFIXED_DIGITS_RE.fullmatch(layer_token)
    if printed is None or not engine_token.startswith(printed["prefix"]):
        return False
    read = engine_token[len(printed["prefix"]):]
    return _changes_type_inside(token_html) and _reads_figures_as_lowercase_letters(read, printed["digits"])


def _changes_type_inside(token_html: str) -> bool:
    return _ITALIC_TAG_RE.search(token_html) is not None


def _reads_figures_as_lowercase_letters(read: str, printed_digits: str) -> bool:
    letters = _LETTER_RE.findall(read)
    read_digits = _DIGIT_RE.findall(read)
    figures_among_letters = bool(letters) and bool(read_digits) and all(letter.islower() for letter in letters)
    return figures_among_letters and _keeps_in_order(read_digits, printed_digits)


def _keeps_in_order(read_digits: list[str], printed_digits: str) -> bool:
    remaining = iter(printed_digits)
    return all(digit in remaining for digit in read_digits)


def _takes_the_curly_form(engine_token: str, layer_token: str) -> bool:
    return layer_token in CURLY_FORMS.get(engine_token, frozenset())


def _is_a_slip(engine_word: str, layer_form: str) -> bool:
    read_letters, printed_letters = _letters_of(engine_word), _letters_of(layer_form)
    return 0 < _edit_distance(read_letters, printed_letters) <= max(1, len(read_letters) // LETTERS_PER_SLIP)


def _letters_of(word: str) -> str:
    return _SLASHED_NUMERAL_RE.sub("", word).replace(HYPHEN, "")


def _edit_distance(first: str, second: str) -> int:
    earlier_row: list[int] = []
    previous_row = list(range(len(second) + 1))
    for row, first_char in enumerate(first, start=1):
        current_row = [row]
        for column, second_char in enumerate(second, start=1):
            substituted = previous_row[column - 1] + (first_char != second_char)
            slips = min(previous_row[column] + 1, current_row[column - 1] + 1, substituted)
            if _swaps_neighbours(first[max(row - PAIR, 0):row], second[max(column - PAIR, 0):column]):
                slips = min(slips, earlier_row[column - 2] + 1)
            current_row.append(slips)
        earlier_row, previous_row = previous_row, current_row
    return previous_row[-1]


def _swaps_neighbours(first_pair: str, second_pair: str) -> bool:
    if len(first_pair) != PAIR or len(second_pair) != PAIR:
        return False
    return first_pair == second_pair[::-1] and first_pair[0] != first_pair[1]
