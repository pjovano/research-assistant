from __future__ import annotations

import re

from _extract.notemarks import raised_mark

_RAISED_NUMBER_TEMPLATE = r"\^(?:\{{\s*{number}\s*\}}|{number})(?!\d)"
_CLOSING_SUPERSCRIPT_TEMPLATE = r"(?<=[^$])" + _RAISED_NUMBER_TEMPLATE + r"(?P<closing>\$\$|\$)"
_WORDS_SUPERSCRIPT_TEMPLATE = (r"(?P<words>\\text\{{[^{{}}$]*\}})" + _RAISED_NUMBER_TEMPLATE
                               + r"(?P<rest>[^$]*)(?P<closing>\$\$|\$)")
_MARK_PLACES = ((_CLOSING_SUPERSCRIPT_TEMPLATE, r"\g<closing>"),
                (_WORDS_SUPERSCRIPT_TEMPLATE, r"\g<words>\g<rest>\g<closing>"))


class FormulaMarks:
    def __init__(self, note_numbers: set[str], marked_numbers: set[str]) -> None:
        self._unmarked = note_numbers - marked_numbers

    def raised(self, html: str) -> str:
        for number in self._unmarked:
            html = self._raised_once(html, number)
        return html

    @staticmethod
    def _raised_once(html: str, number: str) -> str:
        for template, kept in _MARK_PLACES:
            pattern = template.format(number=re.escape(number))
            raised, count = re.subn(pattern, kept + raised_mark(number), html, count=1)
            if count:
                return raised
        return html
