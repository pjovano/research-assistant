from __future__ import annotations

import html
import re
from dataclasses import dataclass

from _extract.blocks import UNPRINTED_RE

_BREAK_RE = re.compile(r"<br\s*/?>|</p>", re.IGNORECASE)
_ITEM_END_RE = re.compile(r"</(?:p|li)>", re.IGNORECASE)
_ITALIC_RE = re.compile(r"<(i|em)>(.*?)</\1>", re.DOTALL)
_BOLD_RE = re.compile(r"<(b|strong)>(.*?)</\1>", re.DOTALL)
_KEPT_TAGS = ("sup", "sub")
_TAG_RE = re.compile(r"</?([A-Za-z0-9]+)[^>]*>")
_SPACES_RE = re.compile(r"[ \t]+")
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(r"<t([hd])([^>]*)>(.*?)</t\1>", re.DOTALL | re.IGNORECASE)
_SPAN_RE = re.compile(r"(row|col)span\s*=\s*\"?(\d+)\"?", re.IGNORECASE)
_SPAN_ATTRIBUTES_RE = re.compile(r"<t[hd]([^>]*)>", re.IGNORECASE)
_SPAN_SUFFIX = "span"
_TABLE_OPEN = "<table>"
_TABLE_RE = re.compile(r"<table\b.*?</table>", re.DOTALL | re.IGNORECASE)
_TABLE_CLOSE = "</table>"
_ESCAPED_KEPT_TAG_RE = re.compile(rf"&lt;(/?(?:{'|'.join(_KEPT_TAGS)}))&gt;")
_PRE_RE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL | re.IGNORECASE)
_CODE_FENCE = "```"
BOLD_MARK = "**"
_BARE_PIPE_RE = re.compile(r"(?<!\\)\|")


class HtmlToMarkdown:
    def text(self, html_text: str) -> str:
        converted = _BREAK_RE.sub("\n", html_text)
        converted = _ITALIC_RE.sub(lambda match: match.group(2), converted)
        converted = _BOLD_RE.sub(lambda match: self._wrapped(match.group(2), BOLD_MARK), converted)
        converted = _TAG_RE.sub(self._kept_or_dropped, converted)
        return self._tidy(html.unescape(converted))

    def items(self, html_text: str) -> list[str]:
        texts = (self.text(item) for item in _ITEM_END_RE.split(html_text))
        return [text for text in texts if text]

    def code(self, html_text: str) -> str:
        match = _PRE_RE.search(html_text)
        source = html.unescape(match.group(1)) if match else self.text(html_text)
        return f"{_CODE_FENCE}\n{source.strip()}\n{_CODE_FENCE}"

    def _wrapped(self, inner: str, marker: str) -> str:
        stripped = inner.strip()
        return f"{marker}{stripped}{marker}" if stripped else inner

    def _kept_or_dropped(self, match: re.Match) -> str:
        return match.group(0) if match.group(1).lower() in _KEPT_TAGS else " "

    def _tidy(self, text: str) -> str:
        readable = UNPRINTED_RE.sub("", text)
        lines = [_SPACES_RE.sub(" ", line).strip() for line in readable.splitlines()]
        return "\n".join(line for line in lines if line)


@dataclass(frozen=True)
class HtmlPiece:
    html: str
    is_table: bool


def table_pieces(html_text: str) -> list[HtmlPiece]:
    tables = list(_TABLE_RE.finditer(html_text))
    if not tables:
        return [HtmlPiece(html_text, True)]
    starts = [0] + [table.end() for table in tables]
    ends = [table.start() for table in tables] + [len(html_text)]
    prose = [HtmlPiece(html_text[start:end], False) for start, end in zip(starts, ends)]
    pieces = [piece for pair in zip(prose, [HtmlPiece(table.group(0), True) for table in tables]) for piece in pair]
    return [piece for piece in pieces + prose[-1:] if piece.is_table or _has_text(piece.html)]


def _has_text(html_text: str) -> bool:
    return bool(_TAG_RE.sub("", html_text).strip())


class TableMarkdown:
    def __init__(self) -> None:
        self._cells = HtmlToMarkdown()

    def text(self, html_text: str) -> str:
        row_htmls = _ROW_RE.findall(html_text)
        if any(_Spans(attributes).spans_cells() for attributes in _SPAN_ATTRIBUTES_RE.findall(html_text)):
            return _SpanningTableHtml(self._cells).of(row_htmls)
        rows = _Grid(self._cells).of(row_htmls)
        if not rows:
            return self._cells.text(html_text)
        width = max(len(row) for row in rows)
        return "\n".join(self._lines(rows, width))

    def _lines(self, rows: list[list[str]], width: int) -> list[str]:
        padded = [row + [""] * (width - len(row)) for row in rows]
        header = "| " + " | ".join(padded[0]) + " |"
        rule = "|" + " --- |" * width
        return [header, rule] + ["| " + " | ".join(row) + " |" for row in padded[1:]]


class _Spans:
    def __init__(self, attributes: str) -> None:
        self._counts = {f"{kind.lower()}{_SPAN_SUFFIX}": int(count) for kind, count in _SPAN_RE.findall(attributes)}

    def spans_cells(self) -> bool:
        return any(count > 1 for count in self._counts.values())

    def html(self) -> str:
        return "".join(f' {name}="{count}"' for name, count in sorted(self._counts.items()) if count > 1)


class _Grid:
    def __init__(self, cells: HtmlToMarkdown) -> None:
        self._cells = cells

    def of(self, row_htmls: list[str]) -> list[list[str]]:
        rows = [[self._text_of(cell) for _kind, _attributes, cell in _CELL_RE.findall(row)] for row in row_htmls]
        return [row for row in rows if any(cell.strip() for cell in row)]

    def _text_of(self, cell_html: str) -> str:
        return _BARE_PIPE_RE.sub("\\|", self._cells.text(cell_html).replace("\n", " "))


class _SpanningTableHtml:
    def __init__(self, cells: HtmlToMarkdown) -> None:
        self._cells = cells

    def of(self, row_htmls: list[str]) -> str:
        rows = [self._row(row_html) for row_html in row_htmls]
        return "\n".join([_TABLE_OPEN, *[row for row in rows if row], _TABLE_CLOSE])

    def _row(self, row_html: str) -> str:
        cells = "".join(self._cell(kind, attributes, cell) for kind, attributes, cell in _CELL_RE.findall(row_html))
        return f"<tr>{cells}</tr>" if cells else ""

    def _cell(self, kind: str, attributes: str, cell_html: str) -> str:
        tag = f"t{kind.lower()}"
        return f"<{tag}{_Spans(attributes).html()}>{self._escaped(cell_html)}</{tag}>"

    def _escaped(self, cell_html: str) -> str:
        text = html.escape(self._cells.text(cell_html).replace("\n", " "), quote=False)
        return _ESCAPED_KEPT_TAG_RE.sub(lambda match: f"<{match.group(1)}>", text)
