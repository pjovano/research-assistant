from __future__ import annotations

import html
import re
import unicodedata

from pylatexenc.latexencode import unicode_to_latex
from pylatexenc.latexwalker import LatexWalker, LatexWalkerError

SUPPLEMENTARY_MACROS = {
    "\\models": "⊨", "\\neg": "¬", "\\lnot": "¬", "\\Box": "□", "\\square": "□", "\\Diamond": "◊",
    "\\diamond": "◊", "\\lozenge": "◊", "\\bot": "⊥", "\\lhd": "◁", "\\rhd": "▷", "\\nvdash": "⊬",
    "\\nmodels": "⊭", "\\Vdash": "⊩", "\\top": "⊤", "\\langle": "⟨", "\\rangle": "⟩", "\\cdot": "·",
    "\\ast": "∗", "\\sqsubseteq": "⊑", "\\sqsupseteq": "⊒", "\\sqsubset": "⊏", "\\sqsupset": "⊐",
    "\\preceq": "⪯", "\\cdots": "···", "\\ldots": "...", "\\dots": "...", "\\succeq": "⪰", "\\prime": "′",
    "\\vDash": "⊨", "\\nvDash": "⊭",
    "\\llbracket": "⟦", "\\rrbracket": "⟧", "\\not": "̸", "\\emptyset": "∅", "\\mid": "|", "\\bigcirc": "◯",
    "\\parr": "⅋", "\\llparenthesis": "⦇", "\\rrparenthesis": "⦈", "\\VDash": "⊫", "\\Dashv": "⫤", "\\dashV": "⫣",
    "\\DashV": "⫥",
}
_MACRO_RE = re.compile(r"\\[A-Za-z]+")
_LAST_ASCII_CODE_POINT = 0x7F
_SCRIPTS = ("_", "^")
_ENSUREMATH_RE = re.compile(r"^\\ensuremath\{(.*)\}$")
_ENSUREMATH_CALL_RE = re.compile(r"\\ensuremath\s*\{")
_CONNECTIVE_WORDS = ("if", "and", "only", "iff", "or", "not", "for", "all", "some", "such", "that", "then", "else",
                     "where", "when", "with", "otherwise", "und", "oder", "genau", "dann", "wenn", "et", "ou", "si",
                     "seulement", "alors")
_CONNECTIVE = "|".join(sorted(_CONNECTIVE_WORDS, key=len, reverse=True))
_CONNECTIVE_RUN_RE = re.compile(rf"(?<![\\A-Za-z])(?:{_CONNECTIVE})(?:\s+(?:{_CONNECTIVE}))*(?![A-Za-z])")
_TEXT_ARGUMENT_CALL_RE = re.compile(r"\\(?:text[a-z]*|mathrm|operatorname|mbox)\s*\{")
_UNSUPPORTED_MACRO_NAMES = ("\\llbracket", "\\rrbracket", "\\parr", "\\llparenthesis", "\\rrparenthesis",
                            "\\VDash", "\\Dashv", "\\dashV", "\\DashV")
_UNSUPPORTED_MACROS = {name: SUPPLEMENTARY_MACROS[name] for name in _UNSUPPORTED_MACRO_NAMES}
_TEXT_FORM_RE = re.compile(r"^\{\\(text[A-Za-z]+)\}$")
_TEXT_TO_MATH = {
    "textlnot": "\\neg", "textrightarrow": "\\rightarrow", "textleftarrow": "\\leftarrow", "texttimes": "\\times",
    "textperiodcentered": "\\cdot", "textuparrow": "\\uparrow", "textdownarrow": "\\downarrow",
    "textopenbullet": "\\circ", "textellipsis": "\\ldots", "textdagger": "\\dagger", "textdiv": "\\div",
    "textbackslash": "\\backslash", "textbigcircle": "\\bigcirc", "textasciicircum": "\\hat{}",
    "textasciitilde": "\\sim", "textbullet": "\\bullet", "textdaggerdbl": "\\ddagger",
}
_ADDED = {
    "−": "-", "∣": "\\mid", "◦": "\\circ", "⋄": "\\diamond", "♢": "\\diamond", "■": "\\blacksquare",
    "▪": "\\blacksquare",
    "∆": "\\Delta", "ϵ": "\\epsilon", "ε": "\\varepsilon", "≠": "\\neq", "⟦": "\\llbracket", "⟧": "\\rrbracket",
    "̸": "\\not", "⊨": "\\models", "⊭": "\\nmodels", "□": "\\Box", "◊": "\\Diamond", "⊥": "\\bot", "◁": "\\lhd",
    "▷": "\\rhd", "∅": "\\emptyset", "′": "\\prime", "∗": "\\ast", "·": "\\cdot", "⋅": "\\cdot", "∙": "\\bullet",
    "•": "\\bullet", "…": "\\ldots", "⊢": "\\vdash", "⊣": "\\dashv", "⋆": "\\star", "◯": "\\bigcirc", "~": "\\sim",
}
_IGNORED_CATEGORIES = ("Mn", "Sk", "Zs", "Cc", "Cf")


def closing_brace_index(latex: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(latex)):
        depth += {"{": 1, "}": -1}.get(latex[index], 0)
        if depth == 0:
            return index
    return None


class MathJaxLatex:
    def safe(self, latex: str) -> str:
        return self._worded(self._unwrapped(_MACRO_RE.sub(self._supported, html.unescape(latex))))

    def _worded(self, latex: str) -> str:
        protected = self._text_arguments(latex)
        return _CONNECTIVE_RUN_RE.sub(lambda match: self._as_text(match, protected), latex)

    @staticmethod
    def _as_text(match: re.Match, protected: list[tuple[int, int]]) -> str:
        if any(start <= match.start() < end for start, end in protected):
            return match.group(0)
        return f"\\text{{ {match.group(0)} }}"

    def _text_arguments(self, latex: str) -> list[tuple[int, int]]:
        arguments = []
        for call in _TEXT_ARGUMENT_CALL_RE.finditer(latex):
            closing = closing_brace_index(latex, call.end() - 1)
            if closing is not None:
                arguments.append((call.end(), closing))
        return arguments

    @staticmethod
    def _supported(match: re.Match) -> str:
        return _UNSUPPORTED_MACROS.get(match.group(0), match.group(0))

    def _unwrapped(self, latex: str) -> str:
        call = _ENSUREMATH_CALL_RE.search(latex)
        if call is None:
            return latex
        closing = closing_brace_index(latex, call.end() - 1)
        if closing is None:
            return latex
        return self._unwrapped(latex[:call.start()] + latex[call.end():closing] + latex[closing + 1:])


def with_supplementary_unicode(latex: str) -> str:
    return _MACRO_RE.sub(lambda match: SUPPLEMENTARY_MACROS.get(match.group(0), match.group(0)), latex)


class MathMacros:
    def __init__(self) -> None:
        self._known: dict[str, str | None] = dict(_ADDED)
        for macro, char in SUPPLEMENTARY_MACROS.items():
            self._known.setdefault(char, macro)

    def macro(self, char: str) -> str | None:
        if char not in self._known:
            self._known[char] = self._encoded(char)
        return self._known[char]

    def _encoded(self, char: str) -> str | None:
        if char in _ADDED or unicodedata.category(char) in _IGNORED_CATEGORIES:
            return _ADDED.get(char)
        encoded = unicode_to_latex(char)
        if encoded == char and ord(char) > _LAST_ASCII_CODE_POINT:
            return None
        return self._math_form(encoded)

    def _math_form(self, encoded: str) -> str | None:
        in_math = _ENSUREMATH_RE.match(encoded)
        if in_math:
            return in_math.group(1)
        text_form = _TEXT_FORM_RE.match(encoded)
        if text_form:
            return _TEXT_TO_MATH.get(text_form.group(1))
        return None if "\\text" in encoded or "\\small" in encoded else encoded


class LatexGate:
    def parses(self, latex: str) -> bool:
        if _ScriptScanner().has_double(latex):
            return False
        try:
            LatexWalker(latex, tolerant_parsing=False).get_latex_nodes()
        except (LatexWalkerError, ValueError):
            return False
        return True


class _ScriptScanner:
    def has_double(self, latex: str) -> bool:
        used: set[str] = set()
        position = 0
        while position < len(latex):
            token, position = self._token(latex, position)
            if not token:
                return False
            if token in _SCRIPTS:
                if token in used:
                    return True
                used.add(token)
                _argument, position = self._token(latex, position)
            else:
                used = set()
        return False

    def _token(self, latex: str, position: int) -> tuple[str, int]:
        while position < len(latex) and latex[position].isspace():
            position += 1
        if position >= len(latex):
            return "", position
        if latex[position] == "{":
            end = self._group_end(latex, position)
            return latex[position:end], end
        macro = _MACRO_RE.match(latex, position)
        if macro:
            return macro.group(0), macro.end()
        return latex[position], position + 1

    @staticmethod
    def _group_end(latex: str, start: int) -> int:
        closing = closing_brace_index(latex, start)
        return len(latex) if closing is None else closing + 1
