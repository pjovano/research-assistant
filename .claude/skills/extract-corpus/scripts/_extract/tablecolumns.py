from __future__ import annotations

import html
import re
from dataclasses import dataclass

from _extract.blocks import TAG_RE, Block
from _extract.layerlines import rows_of
from _extract.layertables import LayerTable

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(r"<t([hd])[^>]*>(.*?)</t\1>", re.DOTALL | re.IGNORECASE)
_SPANNING_RE = re.compile(r"(?:row|col)span\s*=\s*\"?0*(?:[2-9]|[1-9]\d)", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_HEADER_KIND = "h"


@dataclass(frozen=True)
class _Cell:
    kind: str
    html: str

    @property
    def words(self) -> str:
        return _WHITESPACE_RE.sub("", html.unescape(TAG_RE.sub("", self.html)))

    def followed_by(self, other: "_Cell") -> "_Cell":
        return _Cell(self.kind, self.html + other.html)

    def written(self) -> str:
        return f"<t{self.kind}>{self.html}</t{self.kind}>"


class TableColumns:
    def __init__(self, layer, reading) -> None:
        self._layer = layer
        self._reading = reading

    def read(self, block: Block, table_html: str) -> str:
        if _SPANNING_RE.search(table_html):
            return table_html
        rows = [[_Cell(kind.lower(), cell) for kind, cell in _CELL_RE.findall(row)]
                for row in _ROW_RE.findall(table_html)]
        layer_table = LayerTable(self._chars_of(block), self._reading)
        if self._reading.trusts_the_layer(block.file_page) and layer_table.sets_more_columns_than(_width_of(rows)):
            return layer_table.html()
        return self._joined(block, rows, table_html)

    def _joined(self, block: Block, rows: list[list[_Cell]], table_html: str) -> str:
        joined = _JoinedRows(rows, self._printed_words(block)).rows()
        return table_html if joined == rows else _written(joined)

    def _chars_of(self, block: Block) -> list:
        return self._layer.chars_in(block.file_page, block.bbox)

    def _printed_words(self, block: Block) -> set[str]:
        rows = rows_of(self._chars_of(block))
        texts = [html.unescape(TAG_RE.sub("", self._reading.html_of_rows([row]))) for row in rows]
        return {word for text in texts for word in text.split()}


class _JoinedRows:
    def __init__(self, rows: list[list[_Cell]], printed_words: set[str]) -> None:
        self._rows = rows
        self._printed_words = printed_words

    def rows(self) -> list[list[_Cell]]:
        rows, column = self._rows, 1
        while column < max((len(row) for row in rows), default=0):
            if self._prints_as_one_word(rows, column):
                rows = [_with_columns_joined(row, column) for row in rows]
            else:
                column += 1
        return rows

    def _prints_as_one_word(self, rows: list[list[_Cell]], column: int) -> bool:
        body_rows = [row for row in rows if not _is_a_header(row)]
        return bool(body_rows) and all(self._joins_one_word(row, column) for row in body_rows)

    def _joins_one_word(self, row: list[_Cell], column: int) -> bool:
        if len(row) <= column:
            return False
        left, right = row[column - 1].words, row[column].words
        return bool(left) and bool(right) and left + right in self._printed_words


def _width_of(rows: list[list[_Cell]]) -> int:
    return max((len(row) for row in rows), default=0)


def _is_a_header(row: list[_Cell]) -> bool:
    return all(cell.kind == _HEADER_KIND for cell in row)


def _with_columns_joined(row: list[_Cell], column: int) -> list[_Cell]:
    if len(row) <= column:
        return row
    return row[:column - 1] + [row[column - 1].followed_by(row[column])] + row[column + 1:]


def _written(rows: list[list[_Cell]]) -> str:
    return "<table>" + "".join("<tr>" + "".join(cell.written() for cell in row) + "</tr>" for row in rows) + "</table>"
