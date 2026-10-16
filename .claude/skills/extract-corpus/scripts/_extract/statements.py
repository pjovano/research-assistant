from __future__ import annotations

import re

from notation import without_notation

MIN_LABEL_CHARS = 2
MAX_LABEL_CHARS = 80
_LABEL_RE = re.compile(rf"^\*\*\s*(?P<label>[^*\n]{{{MIN_LABEL_CHARS},{MAX_LABEL_CHARS}}}?)\s*\*\*")
_DIGIT_RE = re.compile(r"\d")
_LETTER_OR_DOTTED_NUMBER_RE = re.compile(r"[^\W\d_]|\d\.\d")
_TRAILING_PUNCTUATION = " .:"


class StatementLabel:
    def of(self, text: str) -> str | None:
        label = self.bold_opening(text)
        return label if label is not None and self._names_a_statement(label) else None

    @staticmethod
    def bold_opening(text: str) -> str | None:
        found = _LABEL_RE.match(text.strip())
        return None if found is None else found.group("label").strip(_TRAILING_PUNCTUATION)

    def without(self, text: str) -> str:
        return _LABEL_RE.sub("", text.strip(), count=1).strip()

    @staticmethod
    def _names_a_statement(label: str) -> bool:
        prose = without_notation(label)
        return _DIGIT_RE.search(prose) is not None and _LETTER_OR_DOTTED_NUMBER_RE.search(prose) is not None
