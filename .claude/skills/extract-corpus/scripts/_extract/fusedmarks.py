from __future__ import annotations

import re

from _extract.blocks import FOOTNOTE_KIND, TAG_RE, PageBlocks
from _extract.footnotes import leading_note_number, mark_numbers
from _extract.notemarks import raised_mark

CONTEXT_WORDS = 3
_FUSED_MARK_RE = re.compile(r"(?P<word>[^\W\d_]{2,})(?P<number>\d{1,3})(?=[\s.,;:!?)\]—–-]|$)")
_WORD_RE = re.compile(r"\S+")
_BETWEEN_WORDS = r"(?:\s|<[^>]+>)+"
_UNMARKED_END = r"(?![\w<])"


class FusedMarks:
    def __init__(self, unanswered_numerals: set[str]) -> None:
        self._unanswered_numerals = unanswered_numerals

    @classmethod
    def of_page(cls, page: PageBlocks) -> FusedMarks:
        notes = {leading_note_number(block.plain_text) for block in page.of_kind(FOOTNOTE_KIND)} - {None}
        raised = {number for block in page.content if block.kind != FOOTNOTE_KIND for number in mark_numbers(block.html)}
        return cls(notes - raised)

    def corrected(self, engine_html: str, layer_html: str) -> str:
        layer_text = TAG_RE.sub(" ", layer_html)
        for fused in _FUSED_MARK_RE.finditer(layer_text):
            if fused.group("number") in self._unanswered_numerals:
                words = _WORD_RE.findall(layer_text[:fused.start()])[-CONTEXT_WORDS + 1:] + [fused.group("word")]
                engine_html = _raised_after(engine_html, words, fused.group("number"))
        return engine_html


def _raised_after(engine_html: str, words: list[str], number: str) -> str:
    for taken in range(1, len(words) + 1):
        pattern = _BETWEEN_WORDS.join(re.escape(word) for word in words[-taken:]) + _UNMARKED_END
        found = list(re.finditer(rf"(?<!\w){pattern}", engine_html))
        if len(found) == 1:
            return engine_html[:found[0].end()] + raised_mark(number) + engine_html[found[0].end():]
    return engine_html
