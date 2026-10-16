from __future__ import annotations

import dataclasses

from _extract.blocks import Block
from _extract.blockwriting import HeadingReading
from _extract.footnotes import without_marks
from _extract.headings import HeadingText
from _extract.markdown import HtmlToMarkdown


class PageBlockTexts:
    def __init__(self, content: list[Block], htmls: list[str], reading: HeadingReading) -> None:
        self._content = content
        self._htmls = htmls
        self._reading = reading
        self._markdown = HtmlToMarkdown()

    @property
    def blocks(self) -> list[Block]:
        return self._content

    def blocks_and_htmls(self) -> list[tuple[Block, str]]:
        return list(zip(self._content, self._htmls))

    def plain_text_at(self, index: int) -> str:
        return dataclasses.replace(self._content[index], html=self._htmls[index]).plain_text

    def markdown_at(self, index: int) -> str:
        return self._markdown.text(self._htmls[index])

    def heading_reading_at(self, index: int) -> HeadingText:
        return self._reading.reading(self._content[index], self._htmls[index])

    def heading_text_at(self, index: int) -> str:
        return self._reading.text(self._content[index], self._htmls[index])

    def unmarked_text_at(self, index: int) -> str:
        text, _labels = without_marks(self.heading_text_at(index))
        return text

    def labels_printed_in(self, index: int) -> list[str]:
        _text, labels = without_marks(self.heading_text_at(index))
        return labels

    def marks_printed_in(self, index: int) -> list[str]:
        return list(self.heading_reading_at(index).marks) + self.labels_printed_in(index)

    def line_texts_at(self, index: int) -> list[str]:
        return self._reading.line_texts(self._content[index])
