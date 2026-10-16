from __future__ import annotations

import difflib
import re

_WORD_RE = re.compile(r"[^\W\d_]+")
_LINE_BREAK_HYPHEN_RE = re.compile(r"(\w)-[ \t]*\n\s*(\w)")


class WordSequence:
    def __init__(self, text: str) -> None:
        joined = _LINE_BREAK_HYPHEN_RE.sub(r"\1\2", text)
        self._words = [word.casefold() for word in _WORD_RE.findall(joined)]

    @property
    def count(self) -> int:
        return len(self._words)

    def agreement_with(self, reference: WordSequence) -> float:
        if not reference._words:
            return 0.0
        matcher = difflib.SequenceMatcher(None, self._words, reference._words, autojunk=False)
        matched = sum(block.size for block in matcher.get_matching_blocks())
        return matched / reference.count
