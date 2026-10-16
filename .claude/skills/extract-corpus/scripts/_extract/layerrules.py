from __future__ import annotations

import dataclasses
import re
import statistics
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from _extract.alphabets import lettered
from _extract.box import Box

if TYPE_CHECKING:
    from _extract.layer import LayerChar

MIN_DASH_WIDTH = 8.0
MAX_RULE_HEIGHT = 1.5
DASH_RUN = "——"
WORD_SPACE = " "
CLOSING_PUNCTUATION_CATEGORIES = frozenset({"Pd", "Pe", "Pf", "Po"})
DASH_LOWEST_RISE_SHARE = 0.0
DASH_HIGHEST_RISE_SHARE = 0.5
MAX_DASH_GAP_SHARE = 1.0
MAX_ABUTTING_OVERLAP_SHARE = 0.1
OPAQUE = 1.0
MAX_FRACTION_GAP_SHARE = 0.5
SAME_LINE_SHARE = 0.4
APART_SHARE = 0.5
MAX_RULE_PADDING_SHARE = 1.0
MAX_TERM_GAP_SHARE = 1.0
MIN_PROSE_WORD_LETTERS = 2
MAJORITY_SHARE = 0.5
_LATEX_SPECIAL_RE = re.compile(r"[&%#_{}$]")
_WORD_SPACES_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LayerRule:
    x0: float
    x1: float
    y: float

    def is_as_wide_as_a_dash(self) -> bool:
        return self.x1 - self.x0 >= MIN_DASH_WIDTH


class PageRules:
    def of(self, page, claimed: set[tuple]) -> list[LayerRule]:
        drawn = [rect for rect in _ShownDrawings(page.get_drawings()).rects() if tuple(rect) not in claimed]
        return [self._rule(mark) for mark in drawn + self._painted_images(page) if self._is_rule(mark)]

    @staticmethod
    def _painted_images(page) -> list:
        return [placement for image in page.get_images(full=True) for placement in page.get_image_rects(image[0])]

    @staticmethod
    def _is_rule(mark) -> bool:
        return mark.width > 0 and mark.height <= MAX_RULE_HEIGHT

    @staticmethod
    def _rule(mark) -> LayerRule:
        return LayerRule(mark.x0, mark.x1, (mark.y0 + mark.y1) / 2)


class _ShownDrawings:
    def __init__(self, drawings: list[dict]) -> None:
        self._drawings = drawings
        self._opaque_fills = [drawing for drawing in drawings if _is_opaque_fill(drawing)]

    def rects(self) -> list:
        return [drawing["rect"] for drawing in self._drawings if not self._is_painted_over(drawing)]

    def _is_painted_over(self, drawing: dict) -> bool:
        return any(fill["seqno"] > drawing["seqno"] and fill["rect"].contains(drawing["rect"])
                   for fill in self._opaque_fills)


def _is_opaque_fill(drawing: dict) -> bool:
    return drawing.get("fill") is not None and drawing.get("fill_opacity", OPAQUE) >= OPAQUE


class DrawnDashes:
    def __init__(self, chars: list[LayerChar], rules: list[LayerRule]) -> None:
        inked = [char for char in chars if not char.is_blank]
        read = (_DashReading(rule, inked).dash() for rule in rules if rule.is_as_wide_as_a_dash())
        self._dashes = [dash for dash in read if dash is not None]

    def merged(self, chars: list[LayerChar]) -> list[LayerChar]:
        merged = list(chars)
        lines = {char.line for char in chars}
        for dash in (dash for dash in self._dashes if dash.line in lines):
            merged.insert(position_on_its_line(dash, merged), dash)
        return merged

    def on_line(self, line: int) -> list[LayerChar]:
        return [dash for dash in self._dashes if dash.line == line]


class _DashReading:
    def __init__(self, rule: LayerRule, inked: list[LayerChar]) -> None:
        self._rule = rule
        self._inked = inked

    def dash(self) -> LayerChar | None:
        following = min((char for char in self._inked if self._precedes(char)), key=_left_of, default=None)
        if following is None or any(self._is_stacked_on(char) for char in self._inked):
            return None
        box = Box(self._rule.x0, following.bbox.top, following.bbox.left, following.bbox.bottom)
        return dataclasses.replace(following, char=_dash_run_before(following), raised=False, center=box.center,
                                   origin=(self._rule.x0, following.baseline), bbox=box)

    def _precedes(self, char: LayerChar) -> bool:
        gap = char.bbox.left - self._rule.x1
        rise = char.baseline - self._rule.y
        at_dash_height = DASH_LOWEST_RISE_SHARE * char.size <= rise <= DASH_HIGHEST_RISE_SHARE * char.size
        return -_abutting_overlap(char) <= gap <= MAX_DASH_GAP_SHARE * char.size and at_dash_height

    def _is_stacked_on(self, char: LayerChar) -> bool:
        overlaps = char.bbox.left < self._rule.x1 - _abutting_overlap(char) and char.bbox.right > self._rule.x0
        return overlaps and abs(char.center[1] - self._rule.y) < char.size


class DrawnFractions:
    def __init__(self, chars: list[LayerChar], rules: list[LayerRule]) -> None:
        read = (_FractionReading(rule, chars).fraction() for rule in rules)
        self._fractions = [fraction for fraction in read if fraction is not None]

    def merged(self, chars: list[LayerChar]) -> list[LayerChar]:
        merged = [char for char in chars if not any(fraction.stacks(char) for fraction in self._fractions)]
        for fraction in self._fractions:
            merged.insert(position_on_its_line(fraction.char, merged), fraction.char)
        return merged


@dataclass(frozen=True)
class _Fraction:
    numerator: Box
    denominator: Box
    char: LayerChar

    def stacks(self, char: LayerChar) -> bool:
        return self.numerator.contains(char.center) or self.denominator.contains(char.center)


class _FractionReading:
    def __init__(self, rule: LayerRule, chars: list[LayerChar]) -> None:
        self._rule = rule
        self._chars = chars
        self._inked = [char for char in chars if not char.is_blank]

    def fraction(self) -> _Fraction | None:
        numerator = self._run(lambda char: char.center[1] < self._rule.y and self._lies_over(char))
        denominator = self._run(lambda char: char.center[1] > self._rule.y and self._lies_under(char))
        if not (numerator and denominator) or not all(map(self._sets_a_term, (numerator, denominator))):
            return None
        return _Fraction(_box_of(numerator), _box_of(denominator), self._written(numerator, denominator))

    def _run(self, holds) -> list[LayerChar]:
        spanned = [char for char in self._inked if self._rule.x0 <= char.center[0] <= self._rule.x1 and holds(char)]
        return sorted(spanned, key=_left_of)

    def _lies_over(self, char: LayerChar) -> bool:
        return self._rule.y - char.bbox.bottom <= MAX_FRACTION_GAP_SHARE * char.size

    def _lies_under(self, char: LayerChar) -> bool:
        return char.bbox.top - self._rule.y <= MAX_FRACTION_GAP_SHARE * char.size

    def _sets_a_term(self, run: list[LayerChar]) -> bool:
        return self._stands_apart(run) and self._fills_the_rule(run) and _is_unbroken(run)

    def _fills_the_rule(self, run: list[LayerChar]) -> bool:
        padding = MAX_RULE_PADDING_SHARE * statistics.median(char.size for char in run)
        box = _box_of(run)
        return box.left - self._rule.x0 <= padding and self._rule.x1 - box.right <= padding

    def _stands_apart(self, run: list[LayerChar]) -> bool:
        baseline = statistics.median(char.baseline for char in run)
        size = statistics.median(char.size for char in run)
        reach = APART_SHARE * size
        return not any(char not in run and abs(char.baseline - baseline) <= SAME_LINE_SHARE * size
                       and self._rule.x0 - reach <= char.center[0] <= self._rule.x1 + reach for char in self._inked)

    def _written(self, numerator: list[LayerChar], denominator: list[LayerChar]) -> LayerChar:
        box = Box.union([char.bbox for char in numerator + denominator])
        baseline = (statistics.median(char.baseline for char in numerator)
                    + statistics.median(char.baseline for char in denominator)) / 2
        text = f"$\\frac{{{self._term(numerator)}}}{{{self._term(denominator)}}}$"
        return dataclasses.replace(denominator[0], char=text, raised=False, bold=False, italic=False,
                                   center=box.center, origin=(box.left, baseline), bbox=box)

    def _term(self, run: list[LayerChar]) -> str:
        spaced = _latex_text(self._with_word_spaces(run))
        return f"\\text{{{spaced}}}" if _reads_as_prose(spaced) else _latex_text(run)

    def _with_word_spaces(self, run: list[LayerChar]) -> list[LayerChar]:
        lines = {char.line for char in run}
        left, right = run[0].bbox.left, run[-1].bbox.right
        spaces = [char for char in self._chars
                  if char.is_blank and char.line in lines and left < char.center[0] < right]
        return sorted(run + spaces, key=_left_of)


def _is_unbroken(run: list[LayerChar]) -> bool:
    return all(right.bbox.left - left.bbox.right <= MAX_TERM_GAP_SHARE * left.size for left, right in zip(run, run[1:]))


def _latex_text(run: list[LayerChar]) -> str:
    spelled = _WORD_SPACES_RE.sub(WORD_SPACE, "".join(lettered(char.char, char.font) for char in run))
    return _LATEX_SPECIAL_RE.sub(lambda special: f"\\{special.group(0)}", spelled)


def _reads_as_prose(term: str) -> bool:
    tokens = term.split(WORD_SPACE)
    words = [token for token in tokens if token.isalpha() and len(token) >= MIN_PROSE_WORD_LETTERS]
    return len(words) > MAJORITY_SHARE * len(tokens)


def _box_of(run: list[LayerChar]) -> Box:
    return Box.union([char.bbox for char in run])


def _abutting_overlap(char: LayerChar) -> float:
    return MAX_ABUTTING_OVERLAP_SHARE * char.size


def _dash_run_before(following: LayerChar) -> str:
    closes_a_phrase = unicodedata.category(following.char[:1]) in CLOSING_PUNCTUATION_CATEGORIES
    return DASH_RUN if closes_a_phrase else DASH_RUN + WORD_SPACE


def _left_of(char: LayerChar) -> float:
    return char.bbox.left


def position_on_its_line(placed: LayerChar, chars: list[LayerChar]) -> int:
    for position, char in enumerate(chars):
        if char.line == placed.line and char.center[0] > placed.center[0]:
            return position
    return len(chars)
