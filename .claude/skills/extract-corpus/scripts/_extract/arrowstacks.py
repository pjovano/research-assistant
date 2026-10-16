from __future__ import annotations

import re
from dataclasses import dataclass

from latex_symbols import MathMacros

from _extract.latexgroups import closing_of

ARROW_HEADS = {"→": "\\xrightarrow", "←": "\\xleftarrow"}
SHAFT_CHARS = frozenset("−-")
STACKED_ARROWS = 2
AXIS_SHARE = 0.25
SAME_BASELINE_POINTS = 0.5
MAX_SHAFT_GAP_SHARE = 0.1
MIN_STACK_OVERLAP_SHARE = 0.5
MAX_LABEL_REACH_SHARE = 1.0
SCRIPT_SHIFT_SHARE = 0.2
THIN_SPACE = "\\,"
STACK_TEMPLATE = "\\begin{{matrix}}{upper} \\\\ {lower}\\end{{matrix}}"
LATEX_SPECIALS = frozenset("#$%&~_^\\{}")
_ARROW_COMMAND_RE = re.compile(
    r"\\(?:xrightarrow|xleftarrow|longrightarrow|longleftarrow|rightarrow|leftarrow|to"
    r"|rightrightarrows|leftleftarrows|rightleftarrows|leftrightarrows)(?![A-Za-z])")
_MACRO_END_RE = re.compile(r"\\[A-Za-z]+$")



@dataclass(frozen=True)
class _Arrow:
    command: str
    left: float
    right: float
    line: float
    size: float
    chars: tuple

    def overlap(self, other: _Arrow) -> float:
        return min(self.right, other.right) - max(self.left, other.left)

    def spans(self, char) -> bool:
        return self.left <= char.center[0] <= self.right

    def written(self, over: str, under: str) -> str:
        return f"{self.command}[{under}]{{{over}}}" if under else f"{self.command}{{{over}}}"


class ArrowStack:
    def __init__(self, rows: list[list]) -> None:
        self._chars = [char for row in rows for char in row]
        self._inked = [char for char in self._chars if not char.is_blank]

    def latex(self) -> str | None:
        arrows = _Arrows(self._inked).all()
        if len(arrows) != STACKED_ARROWS:
            return None
        upper, lower = sorted(arrows, key=lambda arrow: arrow.line)
        if not _are_stacked(upper, lower):
            return None
        return _StackLabels(self._chars, upper, lower).latex()


def _are_stacked(upper: _Arrow, lower: _Arrow) -> bool:
    shorter = min(upper.right - upper.left, lower.right - lower.left)
    near = lower.line - upper.line <= max(upper.size, lower.size)
    return near and upper.overlap(lower) >= MIN_STACK_OVERLAP_SHARE * shorter


class _Arrows:
    def __init__(self, inked: list) -> None:
        self._inked = inked

    def all(self) -> list[_Arrow]:
        return [self._arrow(head) for head in self._inked if head.char in ARROW_HEADS]

    def _arrow(self, head) -> _Arrow:
        shaft = self._shaft(head)
        left = min(char.bbox.left for char in shaft)
        right = max(char.bbox.right for char in shaft)
        line = head.baseline - AXIS_SHARE * head.size
        return _Arrow(ARROW_HEADS[head.char], left, right, line, head.size, tuple(map(id, shaft)))

    def _shaft(self, head) -> list:
        shaft = [head]
        pieces = [char for char in self._inked if char.char in SHAFT_CHARS and _on_baseline(char, head)]
        grown = True
        while grown:
            joining = [piece for piece in pieces if piece not in shaft and _touches(piece, shaft)]
            shaft.extend(joining)
            grown = bool(joining)
        return shaft


def _on_baseline(char, head) -> bool:
    return abs(char.baseline - head.baseline) <= SAME_BASELINE_POINTS


def _touches(piece, shaft: list) -> bool:
    reach = MAX_SHAFT_GAP_SHARE * piece.size
    return any(piece.bbox.left <= part.bbox.right + reach and piece.bbox.right >= part.bbox.left - reach
               for part in shaft)


class _StackLabels:
    def __init__(self, chars: list, upper: _Arrow, lower: _Arrow) -> None:
        drawn = set(upper.chars) | set(lower.chars)
        self._chars = [char for char in chars if id(char) not in drawn and upper.spans(char)]
        self._upper = upper
        self._lower = lower

    def latex(self) -> str | None:
        if any(self._is_between(char) for char in self._chars if not char.is_blank):
            return None
        over = _Label([char for char in self._chars if self._is_over(char)]).latex()
        under = _Label([char for char in self._chars if self._is_under(char)]).latex()
        return STACK_TEMPLATE.format(upper=self._upper.written(over, ""), lower=self._lower.written("", under))

    def _is_over(self, char) -> bool:
        return 0 < self._upper.line - char.center[1] <= MAX_LABEL_REACH_SHARE * self._upper.size

    def _is_under(self, char) -> bool:
        return 0 < char.center[1] - self._lower.line <= MAX_LABEL_REACH_SHARE * self._lower.size

    def _is_between(self, char) -> bool:
        return self._upper.line <= char.center[1] <= self._lower.line


class _Label:
    def __init__(self, chars: list) -> None:
        self._chars = sorted(chars, key=lambda char: char.center[0])
        self._macros = MathMacros()

    def latex(self) -> str:
        inked = [char for char in self._chars if not char.is_blank]
        if not inked:
            return ""
        baseline = inked[0].baseline
        written = ""
        for position, char in enumerate(self._chars):
            written = _spaced(written, self._piece(char, baseline) if not char.is_blank else self._space(position))
        return written

    def _piece(self, char, baseline: float) -> str:
        written = self._written(char.char)
        shift = char.baseline - baseline
        if shift > SCRIPT_SHIFT_SHARE * char.size:
            return f"_{{{written}}}"
        if shift < -SCRIPT_SHIFT_SHARE * char.size:
            return f"^{{{written}}}"
        return written

    def _space(self, position: int) -> str:
        inked_around = [char for char in (self._chars[:position][-1:] + self._chars[position + 1:][:1])
                        if not char.is_blank]
        return THIN_SPACE if len(inked_around) == 2 else ""

    def _written(self, char: str) -> str:
        if char.isascii() and char not in LATEX_SPECIALS:
            return char
        return self._macros.macro(char) or char


def _spaced(written: str, piece: str) -> str:
    ends_a_macro_name = _MACRO_END_RE.search(written) is not None
    return f"{written} {piece}" if ends_a_macro_name and piece[:1].isalpha() else written + piece


class ArrowCommand:
    def __init__(self, latex: str) -> None:
        self._latex = latex

    def replaced(self, written: str) -> str | None:
        commands = list(_ARROW_COMMAND_RE.finditer(self._latex))
        if len(commands) != 1:
            return None
        command = commands[0]
        end = self._arguments_end(command.end()) if command.group(0) in ARROW_HEADS.values() else command.end()
        return f"{self._latex[:command.start()]}{written}{self._latex[end:]}"

    def _arguments_end(self, position: int) -> int:
        for opening in "[{":
            position = self._argument_end(position, opening)
        return position

    def _argument_end(self, position: int, opening: str) -> int:
        start = len(self._latex) - len(self._latex[position:].lstrip())
        if not self._latex.startswith(opening, start):
            return position
        closing = closing_of(self._latex, start)
        return position if closing is None else closing + 1
