from __future__ import annotations

from _extract.blockreading import BlockReading
from _extract.blocks import FOOTNOTE_KIND, Block, PageBlocks
from _extract.footnotes import mark_numbers, with_the_layers_numeral
from _extract.markdown import HtmlToMarkdown
from _extract.overlappingnotes import OverlappingNotes
from _extract.policy import SectionPolicy


class FootnoteTexts:
    def __init__(self, reading: BlockReading, policy: SectionPolicy) -> None:
        self._reading = reading
        self._policy = policy
        self._markdown = HtmlToMarkdown()

    def of(self, page: PageBlocks) -> list[str]:
        kept = [block for block in page.of_kind(FOOTNOTE_KIND) if self._policy.keeps_block(block)]
        if self._reading.reads_pixels:
            return [self._pixel_text(block) for block in kept]
        marks = {number for block in page.content for number in mark_numbers(self._reading.body_html(block))}
        overlapping = OverlappingNotes(self._reading.lines, marks)
        return [text for group in overlapping.grouped(kept) for text in self._group_texts(overlapping, group)]

    def _group_texts(self, overlapping: OverlappingNotes, group: list[Block]) -> list[str]:
        lines = self._reading.lines
        if not all(lines.of(block) and not self._reading.is_table(block) for block in group):
            return [self._text(block) for block in group]
        return [self._markdown.text(self._reading.html_of_rows(rows)) for rows in overlapping.notes_of(group)]

    def _pixel_text(self, block: Block) -> str:
        text = self._text(block)
        if not self._reading.trusts_the_layer(block.file_page):
            return text
        return with_the_layers_numeral(text, self._markdown.text(self._reading.built_html(block)))

    def _text(self, block: Block) -> str:
        text = self._markdown.text(self._reading.html_of(block))
        return " ".join(text.splitlines()) if self._reading.is_table(block) else text
