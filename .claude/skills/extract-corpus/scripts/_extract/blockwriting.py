from __future__ import annotations

import dataclasses
import html
from collections import Counter

from _extract.blockreading import BlockReading
from _extract.columnitems import ColumnItemOrder
from _extract.blocks import (
    CAPTION_KIND, CODE_KIND, EQUATION_KIND, LIST_GROUP_KIND, LIST_ITEM_KIND, TEXT_KIND, Block,
)
from _extract.bulletrows import BulletedRows
from _extract.diagramlabels import DiagramLabels
from _extract.elements import LIST_ITEM_BULLET, Paragraph, Verbatim
from _extract.enginemath import MATH_ELEMENT_RE
from _extract.entryopenings import LayerEntryOpenings, follows_a_word
from _extract.footnotes import MARK_RE
from _extract.headings import HeadingKey, HeadingText, LetterSpacedHeading, SmallCapitalFont, rounded_size
from _extract.indents import ParagraphIndents, WorkLayout
from _extract.itemrows import ListItemRows
from _extract.layerlines import WHOLE_PAGE, row_text, rows_of
from _extract.lists import HangingIndentList, ListEntry
from _extract.markdown import HtmlPiece, HtmlToMarkdown, TableMarkdown, table_pieces
from _extract.tablecolumns import TableColumns
from _extract.typesizes import TypeSize


class HeadingReading:
    def __init__(self, layer, reading: BlockReading) -> None:
        self._layer = layer
        self._reading = reading
        self._keys = HeadingKey(layer)

    def text(self, block: Block, html_text: str) -> str:
        return self.reading(block, html_text).text

    def reading(self, block: Block, html_text: str) -> HeadingText:
        marks = tuple(mark.group(0) for mark in MARK_RE.finditer(html_text))
        text = dataclasses.replace(block, html=MARK_RE.sub("", html_text)).plain_text
        chars = self._layer.chars_in(block.file_page, block.bbox)
        reading = LetterSpacedHeading(self._measurable(block, chars)).reading(text)
        return dataclasses.replace(reading, marks=marks, small_capitals=SmallCapitalFont(chars).sets())

    def _measurable(self, block: Block, chars: list) -> list:
        return chars if self._reading.trusts_the_layer(block.file_page) else []

    def key(self, block: Block) -> tuple:
        return self._keys.of(block)

    def trusts_the_layer(self, file_page: int) -> bool:
        return self._reading.trusts_the_layer(file_page)

    def line_sizes(self, block: Block) -> list[float]:
        lines = self._reading.lines
        sizes = [TypeSize([row]).median() for row in lines.of(block)] if lines is not None else []
        return [rounded_size(size) for size in sizes if size is not None]

    def line_texts(self, block: Block) -> list[str]:
        lines = self._reading.lines
        return [row_text(row) for row in lines.of(block)] if lines is not None else []

    def sets_its_letters_in_small_capitals(self, block: Block) -> bool:
        letters = [char for char in self._layer.chars_in(block.file_page, block.bbox) if char.char.isalpha()]
        return SmallCapitalFont(letters).sets()


class BlockWriting:
    def __init__(self, layer, reading: BlockReading) -> None:
        self._layer = layer
        self._reading = reading
        self._lists = HangingIndentList(layer)
        self._markdown = HtmlToMarkdown()
        self._tables = TableMarkdown()
        self._columns = TableColumns(layer, reading)
        self._indents: ParagraphIndents | None = None
        self._diagram_labels: DiagramLabels | None = None
        self._bullets = BulletedRows(None, [])
        self._work_layout = WorkLayout()

    def read_page(self, content: list[Block]) -> None:
        self._indents = ParagraphIndents(self._reading.lines, content, self._work_layout)
        self._work_layout = self._work_layout.after(self._indents)
        self._diagram_labels = DiagramLabels(self._reading.lines, content)
        self._bullets = BulletedRows(self._reading.lines, self._page_shapes(content))

    def _page_shapes(self, content: list[Block]) -> list:
        return self._layer.shapes_in(content[0].file_page, WHOLE_PAGE) if content else []

    def converted(self, block: Block, html_text: str) -> list:
        if block.is_image:
            return self._labels_of(block)
        if self._reading.is_table(block):
            return self._tabled(block, html_text)
        if block.kind == CODE_KIND:
            return [Verbatim(self._markdown.code(html_text), block.file_page)]
        return self._prose(block, html_text)

    def _tabled(self, block: Block, html_text: str) -> list:
        pieces = table_pieces(html_text)
        last = len(pieces) - 1
        return [element for position, piece in enumerate(pieces)
                for element in self._piece(block if position == last else _ending_here(block), piece)]

    def _piece(self, block: Block, piece: HtmlPiece) -> list:
        if piece.is_table:
            return [Verbatim(self._tables.text(self._columns.read(block, piece.html)), block.file_page)]
        return self._prose(block, piece.html)

    def _labels_of(self, block: Block) -> list:
        if self._diagram_labels is None or not self._reading.trusts_the_layer(block.file_page):
            return []
        return self._diagram_labels.of(block)

    def text_of(self, html_text: str) -> str:
        return self._markdown.text(html_text)

    def hanging_entries(self, file_page: int, blocks: list[Block]) -> list[ListEntry]:
        return self._lists.boxed_entries(file_page, [block.bbox for block in blocks])

    def entry_paragraphs(self, file_page: int, entries: list[ListEntry], held: list[tuple[Block, str]]) -> list:
        notation = _notation_readings(entries, held) if self._reading.reads_pixels else {}
        return [Paragraph(self._entry_text(file_page, entry, notation.get(entry)), False, file_page)
                for entry in entries]

    def sets_a_label_list(self, block: Block) -> bool:
        if block.kind == LIST_GROUP_KIND or self._raises_a_mark(block):
            return False
        if self._lists.sets_a_label_column(block.file_page, [block.bbox]):
            return True
        return block.kind == TEXT_KIND and self._lists.runs_labels_into_entries(block.file_page, [block.bbox])

    def _raises_a_mark(self, block: Block) -> bool:
        return any(char.raised for char in self._layer.chars_in(block.file_page, block.bbox))

    def is_numbered_list(self, file_page: int, blocks: list[Block]) -> bool:
        return self._lists.is_numbered(file_page, [block.bbox for block in blocks])

    def trusts_the_layer(self, file_page: int) -> bool:
        return self._reading.trusts_the_layer(file_page)

    def _entry_text(self, file_page: int, entry: ListEntry, engine_html: str | None) -> str:
        if engine_html is not None:
            return self._markdown.text(engine_html)
        rows = rows_of(self._layer.chars_in(file_page, entry.bbox))
        return self._markdown.text(self._reading.html_of_rows(rows) or html.escape(entry.text, quote=False))

    def _prose(self, block: Block, html_text: str) -> list:
        text = self._markdown.text(html_text)
        if not text:
            return []
        if block.kind == LIST_ITEM_KIND:
            return _items(block, self._list_items(block, text))
        if block.kind == CAPTION_KIND:
            return [Paragraph(text, False, block.file_page, is_caption=True)]
        if block.kind == EQUATION_KIND:
            return [Paragraph(text, False, block.file_page)]
        return self._text_block(block, html_text, text)

    def _text_block(self, block: Block, html_text: str, text: str) -> list:
        bulleted = self._bullets.openings(block) if block.kind == TEXT_KIND else []
        if bulleted:
            items = LayerEntryOpenings(self._layer_paragraphs(block, bulleted), follows_a_word).entries(text)
            return _items(block, items)
        return self._paragraphs(block, self._opened_at_their_indents(block, self._markdown.items(html_text)))

    def _list_items(self, block: Block, text: str) -> list[str]:
        items = ListItemRows(self._row_texts(block)).items()
        return LayerEntryOpenings(items).entries(text) if len(items) > 1 else [text]

    def _row_texts(self, block: Block) -> list[str]:
        lines = self._reading.lines
        return [row_text(row) for row in lines.of(block)] if lines is not None else []

    def _opened_at_their_indents(self, block: Block, items: list[str]) -> list[str]:
        openings = self._indents.openings(block) if self._indents is not None and block.kind == TEXT_KIND else []
        if not openings:
            return items
        layer_paragraphs = LayerEntryOpenings(self._layer_paragraphs(block, [0, *openings]))
        return [paragraph for item in items for paragraph in layer_paragraphs.entries(item)]

    def _layer_paragraphs(self, block: Block, starts: list[int]) -> list[str]:
        rows = self._row_texts(block)
        return [" ".join(rows[start:end]) for start, end in zip(starts, [*starts[1:], len(rows)])]

    def _paragraphs(self, block: Block, items: list[str]) -> list[Paragraph]:
        items = ColumnItemOrder(self._lists).ordered(block, items)
        last = len(items) - 1
        return [Paragraph(item, block.continues and index == last, block.file_page,
                          self._resumes(block) and index == 0) for index, item in enumerate(items)]

    def _resumes(self, block: Block) -> bool:
        return self._indents is not None and self._indents.resumes(block)


def _items(block: Block, texts: list[str]) -> list[Verbatim]:
    return [Verbatim(f"{LIST_ITEM_BULLET}{text}", block.file_page) for text in texts]


def _ending_here(block: Block) -> Block:
    return dataclasses.replace(block, html="", continued=False)


def _notation_readings(entries: list[ListEntry], held: list[tuple[Block, str]]) -> dict[ListEntry, str]:
    holding = [(entry, block, html_text) for block, html_text in held for entry in entries
               if block.bbox.contains(entry.bbox.center)]
    entry_counts = Counter(entry for entry, _block, _html in holding)
    block_counts = Counter(block.identifier for _entry, block, _html in holding)
    return {entry: html_text for entry, block, html_text in holding
            if entry_counts[entry] == 1 and block_counts[block.identifier] == 1
            and entry.bbox.contains(block.bbox.center) and MATH_ELEMENT_RE.search(block.html)}
