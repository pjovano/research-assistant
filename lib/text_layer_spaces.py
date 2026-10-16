from __future__ import annotations

import re

RAW_DICTIONARY = "rawdict"
SPACE = " "
MAX_ADVANCE_POINTS = 0.5
CONTEXT_CHARS = 3
X0, X1 = 0, 2
LIGATURE_BEFORE_A_SPACE_RE = re.compile("[ﬀ-ﬆ] \\w")


class ZeroAdvanceSpaces:
    def __init__(self, page) -> None:
        self._page = page

    def closed(self, text: str) -> str:
        if not LIGATURE_BEFORE_A_SPACE_RE.search(text):
            return text
        for spaced, joined in self._joins():
            text = text.replace(spaced, joined)
        return text

    def _joins(self) -> list[tuple[str, str]]:
        return [join for chars in line_characters(self._page.get_text(RAW_DICTIONARY)) for join in _joins_in(chars)]


def takes_no_advance(chars: list[dict], index: int) -> bool:
    if not 0 < index < len(chars) - 1:
        return False
    before, char, after = chars[index - 1], chars[index], chars[index + 1]
    inside_a_word = before["c"].isalpha() and after["c"].isalpha()
    return char["c"] == SPACE and inside_a_word and after["bbox"][X0] - before["bbox"][X1] <= MAX_ADVANCE_POINTS


def line_characters(page: dict) -> list[list[dict]]:
    return [[char for span in line["spans"] for char in span["chars"]]
            for block in page.get("blocks", []) for line in block.get("lines", [])]


def _joins_in(chars: list[dict]) -> list[tuple[str, str]]:
    line = "".join(char["c"] for char in chars)
    return [(line[max(0, index - CONTEXT_CHARS):index + CONTEXT_CHARS + 1],
             line[max(0, index - CONTEXT_CHARS):index] + line[index + 1:index + CONTEXT_CHARS + 1])
            for index in range(len(chars)) if takes_no_advance(chars, index)]
