from __future__ import annotations

import re
import statistics
import string

from _extract.blocks import TEXT_KIND, UNPRINTED_RE, Block
from _extract.elements import Verbatim
from _extract.layerlines import PageLines, row_text
from _extract.strays import NOTE_TYPE_SHARE
from _extract.typesizes import TypeSize

MIN_WORD_LETTERS = 3
MIN_WORD_SHARE = 0.5
LABEL_LINE_SEPARATOR = "\n"
_WORD_RE = re.compile(rf"[^\W\d_]{{{MIN_WORD_LETTERS},}}")


class DiagramLabels:
    def __init__(self, lines: PageLines, content: list[Block]) -> None:
        self._lines = lines
        sizes = [TypeSize(lines.of(block)).median() for block in content if block.kind == TEXT_KIND]
        known = [size for size in sizes if size is not None]
        self._body_size = statistics.median(known) if known else None

    def of(self, block: Block) -> list[Verbatim]:
        rows = [row for row in self._lines.of(block) if _printed_text(row)]
        if not (self._sets_in_the_body_type(rows) and _reads_as_words(rows)):
            return []
        return [Verbatim(LABEL_LINE_SEPARATOR.join(_printed_text(row) for row in rows), block.file_page)]

    def _sets_in_the_body_type(self, rows: list[list]) -> bool:
        size = TypeSize(rows).median()
        if size is None or self._body_size is None:
            return False
        return NOTE_TYPE_SHARE * self._body_size <= size <= self._body_size / NOTE_TYPE_SHARE


def _reads_as_words(rows: list[list]) -> bool:
    tokens = [token.strip(string.punctuation) for row in rows for token in _printed_text(row).split()]
    words = [token for token in tokens if _WORD_RE.fullmatch(token)]
    return bool(tokens) and len(words) >= MIN_WORD_SHARE * len(tokens)


def _printed_text(row: list) -> str:
    return " ".join(UNPRINTED_RE.sub("", row_text(row)).split())
