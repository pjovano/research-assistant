from __future__ import annotations

import re

from _extract.notemarks import raised_mark

_SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_TO_SUPERSCRIPT = str.maketrans("0123456789", _SUPERSCRIPT_DIGITS)
_WHOLE_RUN_TEMPLATE = rf"(?:<sup>\s*)?(?<![{_SUPERSCRIPT_DIGITS}]){{digits}}(?![{_SUPERSCRIPT_DIGITS}])(?:\s*</sup>)?"



class SuperscriptMarks:
    def __init__(self, note_numbers: set[str], marked_numbers: set[str]) -> None:
        self._unmarked = note_numbers - marked_numbers

    def raised(self, html: str) -> str:
        for number in self._unmarked:
            pattern = _WHOLE_RUN_TEMPLATE.format(digits=number.translate(_TO_SUPERSCRIPT))
            html = re.sub(pattern, raised_mark(number), html, count=1)
        return html
