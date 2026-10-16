from __future__ import annotations

import re
import unicodedata

OPEN_DELIMITER = "❲"
CLOSE_DELIMITER = "❳"
INLINE_MATH = "$"
DISPLAY_MATH = "$$"
_PLACEHOLDER_PATTERN = rf"{OPEN_DELIMITER}[^{OPEN_DELIMITER}{CLOSE_DELIMITER}]*{CLOSE_DELIMITER}"
_DISPLAY_LATEX_PATTERN = r"\$\$(?:[^$]|\$(?!\$))+?\$\$"
_INLINE_LATEX_PATTERN = r"(?<![$\\\w])\$(?![\s$\d])(?:[^$\n\\]|\\.)+?(?<!\s)\$(?![$\d])"
DELIMITED_SPAN_RE = re.compile(f"{_PLACEHOLDER_PATTERN}|{_DISPLAY_LATEX_PATTERN}|{_INLINE_LATEX_PATTERN}")
_NON_NEWLINE_RE = re.compile(r"[^\n]")
_DELIMITERS = f"{INLINE_MATH}{OPEN_DELIMITER}{CLOSE_DELIMITER}"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏  ‪-‮﻿]")
_GREEK = range(0x0370, 0x0400)
_LETTERLIKE = range(0x2100, 0x2150)
_MATH_OPERATORS = range(0x2200, 0x2300)
_SYMBOL_CATEGORY = "S"
_IGNORED_CATEGORIES = ("Mn", "Sk")


def delimited_spans(text: str) -> list[str]:
    return [match.group(0) for match in DELIMITED_SPAN_RE.finditer(text)]


def without_notation(text: str, replacement: str = " ") -> str:
    return DELIMITED_SPAN_RE.sub(replacement, text)


def unwrapped_notation(text: str) -> str:
    return DELIMITED_SPAN_RE.sub(lambda match: match.group(0).strip(_DELIMITERS), text)


def blanked_notation(text: str) -> str:
    return DELIMITED_SPAN_RE.sub(lambda match: _NON_NEWLINE_RE.sub(" ", match.group(0)), text)


def inline_latex_span(latex: str) -> str:
    return _delimited_latex(latex, INLINE_MATH)


def display_latex_span(latex: str) -> str:
    return _delimited_latex(latex, DISPLAY_MATH)


def latex_span(latex: str, displayed: bool) -> str:
    return display_latex_span(latex) if displayed else inline_latex_span(latex)


def _delimited_latex(latex: str, delimiter: str) -> str:
    expression = _CONTROL_RE.sub("", latex).strip()
    if not expression:
        return ""
    return f"{delimiter}{expression}{delimiter}"


def inside_notation(position: int, text: str) -> bool:
    return any(match.start() <= position < match.end() for match in DELIMITED_SPAN_RE.finditer(text))


def is_symbol(char: str) -> bool:
    category = unicodedata.category(char)
    if category in _IGNORED_CATEGORIES:
        return False
    code = ord(char)
    return category.startswith(_SYMBOL_CATEGORY) or code in _GREEK or code in _LETTERLIKE or code in _MATH_OPERATORS
