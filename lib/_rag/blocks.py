from __future__ import annotations

from dataclasses import dataclass

from page_marker import PageMarker

from .markdown import (
    HEADING_PATH_SEPARATOR,
    LINE_JOIN,
    Heading,
    InlineMarkup,
    LineKind,
    is_display_math_delimiter,
    line_kind,
)


@dataclass(frozen=True)
class Block:
    text: str
    atomic: bool
    first_page: PageMarker
    last_page: PageMarker


@dataclass(frozen=True)
class Section:
    heading_path: str
    blocks: tuple[Block, ...]


class _OpenBlock:
    def __init__(self, page: PageMarker, atomic: bool) -> None:
        self._lines: list[str] = []
        self._atomic = atomic
        self._first_page = page
        self._last_page = page

    @property
    def atomic(self) -> bool:
        return self._atomic

    def add(self, line: str) -> None:
        self._lines.append(line)

    def turn_page(self, page: PageMarker) -> None:
        self._last_page = page

    def closed(self) -> Block | None:
        text = InlineMarkup.cleaned(LINE_JOIN.join(self._lines)).strip()
        if not text:
            return None
        return Block(text, self._atomic, self._first_page, self._last_page)


class _HeadingStack:
    def __init__(self) -> None:
        self._headings: list[Heading] = []

    def push(self, heading: Heading) -> None:
        while self._headings and self._headings[-1].level >= heading.level:
            self._headings.pop()
        self._headings.append(heading)

    def path(self) -> str:
        return HEADING_PATH_SEPARATOR.join(heading.text for heading in self._headings)


class BodyParser:
    def __init__(self) -> None:
        self._page = PageMarker()
        self._headings = _HeadingStack()
        self._sections: list[Section] = []
        self._blocks: list[Block] = []
        self._open: _OpenBlock | None = None
        self._in_display_math = False

    def sections(self, body: str) -> list[Section]:
        for line in body.splitlines():
            self._take(line)
        self._close_section()
        return [section for section in self._sections if section.blocks]

    def _take(self, line: str) -> None:
        if self._in_display_math:
            self._take_math_line(line)
        else:
            self._HANDLERS[line_kind(line)](self, line)

    def _take_heading(self, line: str) -> None:
        self._close_section()
        self._headings.push(Heading.parsed(line))

    def _take_page_marker(self, line: str) -> None:
        self._turn_page(PageMarker.parsed(line))

    def _take_blank(self, _line: str) -> None:
        self._close_block()

    def _take_footnote_definition(self, line: str) -> None:
        self._open_atomic_with(line)
        self._close_block()

    def _take_math_delimiter(self, line: str) -> None:
        self._open_atomic_with(line)
        self._in_display_math = True

    def _open_atomic_with(self, line: str) -> None:
        self._start_atomic_block()
        self._add_to_open(line)

    def _take_math_line(self, line: str) -> None:
        if PageMarker.parsed(line) is not None:
            self._take_page_marker(line)
        else:
            self._add_math_line(line)

    def _add_math_line(self, line: str) -> None:
        self._add_to_open(line)
        if is_display_math_delimiter(line):
            self._in_display_math = False
            self._close_block()

    def _take_table_line(self, line: str) -> None:
        if self._open is None or not self._open.atomic:
            self._start_atomic_block()
        self._add_to_open(line)

    def _take_prose_line(self, line: str) -> None:
        if self._open is None or self._open.atomic:
            self._start_prose_block()
        self._add_to_open(line)

    def _add_to_open(self, line: str) -> None:
        self._open.add(line)
        for page in PageMarker.inline(line):
            self._turn_page(page)

    def _turn_page(self, page: PageMarker) -> None:
        self._page = page
        if self._open is not None:
            self._open.turn_page(page)

    def _start_atomic_block(self) -> None:
        self._start(_OpenBlock(self._page, atomic=True))

    def _start_prose_block(self) -> None:
        self._start(_OpenBlock(self._page, atomic=False))

    def _start(self, block: _OpenBlock) -> None:
        self._close_block()
        self._open = block

    def _close_block(self) -> None:
        if self._open is None:
            return
        block = self._open.closed()
        self._open = None
        if block is not None:
            self._blocks.append(block)

    def _close_section(self) -> None:
        self._close_block()
        self._sections.append(Section(self._headings.path(), tuple(self._blocks)))
        self._blocks = []

    _HANDLERS = {
        LineKind.HEADING: _take_heading,
        LineKind.PAGE_MARKER: _take_page_marker,
        LineKind.BLANK: _take_blank,
        LineKind.FOOTNOTE_DEFINITION: _take_footnote_definition,
        LineKind.DISPLAY_MATH_DELIMITER: _take_math_delimiter,
        LineKind.TABLE: _take_table_line,
        LineKind.PROSE: _take_prose_line,
    }
