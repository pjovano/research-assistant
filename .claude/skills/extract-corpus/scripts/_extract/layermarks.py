from __future__ import annotations

import dataclasses
import math
import unicodedata
from typing import TYPE_CHECKING, NamedTuple

import accents

from _extract.box import Box

if TYPE_CHECKING:
    from _extract.layer import LayerChar

BASELINE_TOLERANCE_POINTS = 0.5
MACRON = "¯"
HYPHENS = frozenset("-‐")
ACCENT_AND_LETTER = 2


class _DrawnMark(NamedTuple):
    char: str
    x: float
    baseline: float


class DrawnMarks:
    def __init__(self, page) -> None:
        self._page = page
        self._marks: list[_DrawnMark] | None = None

    def placed(self, chars: list[LayerChar]) -> list[LayerChar]:
        if not any(unicodedata.combining(char.char) for char in chars):
            return chars
        unclaimed = list(self._drawn())
        return [self._placed(char, unclaimed) if unicodedata.combining(char.char) else char for char in chars]

    def _drawn(self) -> list[_DrawnMark]:
        if self._marks is None:
            self._marks = [_DrawnMark(chr(char[0]), char[2][0], char[2][1])
                           for span in self._page.get_texttrace() for char in span["chars"]
                           if unicodedata.combining(chr(char[0]))]
        return self._marks

    @staticmethod
    def _placed(mark: LayerChar, unclaimed: list[_DrawnMark]) -> LayerChar:
        candidates = [drawn for drawn in unclaimed if _may_be_drawn_as(mark, drawn)]
        if not candidates:
            return mark
        drawn = min(candidates, key=lambda candidate: candidate.x)
        unclaimed.remove(drawn)
        box = Box(drawn.x, mark.bbox.top, drawn.x, mark.bbox.bottom)
        return dataclasses.replace(mark, origin=(drawn.x, mark.origin[1]), bbox=box, center=box.center)


def _may_be_drawn_as(mark: LayerChar, drawn: _DrawnMark) -> bool:
    on_its_baseline = abs(drawn.baseline - mark.baseline) <= BASELINE_TOLERANCE_POINTS
    at_or_after_it = drawn.x >= mark.origin[0] - BASELINE_TOLERANCE_POINTS
    return drawn.char == mark.char and on_its_baseline and at_or_after_it


class AccentedChars:
    def merged(self, chars: list[LayerChar]) -> list[LayerChar]:
        kept = [char for position, char in enumerate(chars) if not _is_blank_under_an_accented_letter(chars, position)]
        return self._merged_into_following(self._merged_into_preceding(_OverstruckLetters(kept).merged()))

    def _merged_into_preceding(self, chars: list[LayerChar]) -> list[LayerChar]:
        merged: list[LayerChar] = []
        for char in chars:
            letter = self._letter_drawn_under(merged[-1], char) if merged else None
            if letter is None:
                merged.append(char)
            else:
                merged[-1] = dataclasses.replace(merged[-1], char=letter)
        return merged

    def _merged_into_following(self, chars: list[LayerChar]) -> list[LayerChar]:
        merged: list[LayerChar] = []
        carried: dict[int, str] = {}
        for position, char in enumerate(chars):
            carrying = None if position in carried else _MarkCarrier(chars, position).carrying()
            if carrying is None:
                merged.append(dataclasses.replace(char, char=carried.get(position, char.char)))
            else:
                carried.update([carrying])
        return merged

    def _letter_drawn_under(self, base: LayerChar, accent: LayerChar) -> str | None:
        spacing_accent = _spacing_accent_drawn_over(base, accent)
        if spacing_accent is None:
            return None
        composed = accents.composed_either_side(base.char + spacing_accent)
        return composed if len(composed) == 1 else None


class _OverstruckLetters:
    def __init__(self, chars: list[LayerChar]) -> None:
        self._chars = chars

    def merged(self) -> list[LayerChar]:
        return [self._lettered(position) for position in range(len(self._chars)) if not self._is_overstrike(position)]

    def _lettered(self, position: int) -> LayerChar:
        letter = self._chars[position]
        overstrikes = [neighbour for neighbour in self._neighbours(position) if _is_drawn_over(neighbour, letter)]
        return dataclasses.replace(letter, char=overstrikes[0].char) if overstrikes else letter

    def _is_overstrike(self, position: int) -> bool:
        return any(_is_drawn_over(self._chars[position], neighbour) for neighbour in self._neighbours(position))

    def _neighbours(self, position: int) -> list[LayerChar]:
        return self._chars[max(position - 1, 0):position] + self._chars[position + 1:position + 2]


def _is_drawn_over(accented: LayerChar, letter: LayerChar) -> bool:
    decomposed = unicodedata.normalize("NFD", accented.char)
    is_its_accented_form = len(decomposed) > 1 and decomposed[0] == letter.char
    is_inside_it = letter.bbox.left <= accented.center[0] <= letter.bbox.right
    return accented.line == letter.line and is_its_accented_form and is_inside_it


def _is_blank_under_an_accented_letter(chars: list[LayerChar], position: int) -> bool:
    following = chars[position + 1:position + 1 + ACCENT_AND_LETTER]
    if not chars[position].is_blank or len(following) < ACCENT_AND_LETTER:
        return False
    accent, letter = following
    return _accents_a_letter_drawn_over(chars[position], accent, letter)


def _accents_a_letter_drawn_over(blank: LayerChar, accent: LayerChar, letter: LayerChar) -> bool:
    on_one_line = blank.line == accent.line == letter.line
    composes = len(accents.composed(accent.char + letter.char)) == 1
    return on_one_line and composes and letter.bbox.left < blank.bbox.right


def _spacing_accent_drawn_over(base: LayerChar, accent: LayerChar) -> str | None:
    if base.line != accent.line or accent.bbox.right > base.bbox.right:
        return None
    if accent.char in accents.COMBINING_FOR_SPACING:
        return accent.char
    return MACRON if _is_hyphen_raised_inside(base, accent) else None


def _is_hyphen_raised_inside(base: LayerChar, hyphen: LayerChar) -> bool:
    is_raised = hyphen.baseline < base.baseline - BASELINE_TOLERANCE_POINTS
    return hyphen.char in HYPHENS and hyphen.bbox.left >= base.bbox.left and is_raised


class _MarkCarrier:
    def __init__(self, chars: list[LayerChar], position: int) -> None:
        self._chars = chars
        self._position = position
        self._mark = chars[position]

    def carrying(self) -> tuple[int, str] | None:
        carrier = self._carrier_position()
        if carrier is None:
            return None
        composed = self._composed(self._chars[carrier].char)
        return (carrier, composed) if len(composed) == 1 else None

    def _carrier_position(self) -> int | None:
        if not unicodedata.combining(self._mark.char):
            return self._on_mark_line(self._position + 1)
        after = self._on_mark_line(self._past_blanks(self._position + 1))
        return after if after is not None and self._is_drawn_nearer_to(after) else None

    def _is_drawn_nearer_to(self, after: int) -> bool:
        before = self._on_mark_line(self._before_blanks(self._position - 1))
        gap_before = math.inf if before is None else self._gap_to(self._chars[before])
        return self._gap_to(self._chars[after]) < gap_before

    def _gap_to(self, char: LayerChar) -> float:
        drawn_at = self._mark.origin[0]
        return max(char.bbox.left - drawn_at, drawn_at - char.bbox.right, 0.0)

    def _past_blanks(self, position: int) -> int:
        while position < len(self._chars) and self._chars[position].is_blank:
            position += 1
        return position

    def _before_blanks(self, position: int) -> int:
        while position >= 0 and self._chars[position].is_blank:
            position -= 1
        return position

    def _on_mark_line(self, position: int) -> int | None:
        is_on_line = 0 <= position < len(self._chars) and self._chars[position].line == self._mark.line
        return position if is_on_line else None

    def _composed(self, base: str) -> str:
        if unicodedata.combining(self._mark.char):
            return unicodedata.normalize("NFC", base + self._mark.char)
        return accents.composed(self._mark.char + base)
