from __future__ import annotations

from dataclasses import dataclass

import vault as vault_lib
from pagetext import TOP_LEVEL
from page_marker import PageMarker

from .chunking import FILE_PAGE_FIRST_KEY, FOLIO_FIRST_KEY, FOLIO_LAST_KEY, HEADING_PATH_KEY, TIME_FIRST_KEY
from .markdown import HEADING_PATH_SEPARATOR, Heading, InlineMarkup, LineKind, line_kind
from .reports import ERROR_KEY



@dataclass
class _Entry:
    text: str
    path: str
    level: int
    first_page: PageMarker
    last_folio: str | None
    words: int = 0

    def turn_page(self, page: PageMarker) -> None:
        if page.folio:
            self.last_folio = page.folio

    def count(self, line: str) -> None:
        self.words += len(InlineMarkup.cleaned(line).split())

    def rendered(self) -> dict:
        return {HEADING_PATH_KEY: self.path, "level": self.level,
                FOLIO_FIRST_KEY: self.first_page.folio, FOLIO_LAST_KEY: self.last_folio,
                FILE_PAGE_FIRST_KEY: self.first_page.file_page, TIME_FIRST_KEY: self.first_page.time,
                "words": self.words}


class _HeadingTree:
    def __init__(self) -> None:
        self._page = PageMarker()
        self._open: list[_Entry] = []
        self._entries: list[_Entry] = []

    def take(self, line: str) -> None:
        kind = line_kind(line)
        if kind is LineKind.HEADING:
            self._take_heading(Heading.parsed(line))
        elif kind is LineKind.PAGE_MARKER:
            self._turn_page(PageMarker.parsed(line))
        else:
            self._take_body_line(line)

    def entries(self) -> list[dict]:
        self._close_from(TOP_LEVEL)
        return [entry.rendered() for entry in self._entries]

    def words(self) -> int:
        return sum(entry.words for entry in self._entries)

    def _take_heading(self, heading: Heading) -> None:
        self._close_from(heading.level)
        entry = _Entry(heading.text, self._path_with(heading.text), heading.level, self._page, self._page.folio)
        self._open.append(entry)
        self._entries.append(entry)

    def _path_with(self, text: str) -> str:
        return HEADING_PATH_SEPARATOR.join([entry.text for entry in self._open] + [text])

    def _close_from(self, level: int) -> None:
        while self._open and self._open[-1].level >= level:
            self._open.pop()

    def _take_body_line(self, line: str) -> None:
        for page in PageMarker.inline(line):
            self._turn_page(page)
        if self._entries:
            self._entries[-1].count(line)

    def _turn_page(self, page: PageMarker) -> None:
        self._page = page
        for entry in self._open:
            entry.turn_page(page)


class CorpusOutline:
    @classmethod
    def of(cls, basename: str) -> dict:
        path = vault_lib.note_path_for(basename)
        if not path.exists():
            return {ERROR_KEY: f"'{basename}' has no corpus file in {vault_lib.CORPUS_DIR} "
                             f"and no transcript in {vault_lib.TRANSCRIPTS_DIR}"}
        _meta, body = vault_lib.read_frontmatter(path)
        tree = cls._tree(vault_lib.body_after_source_link(body))
        return {"basename": basename, "words": tree.words(), "outline": tree.entries()}

    @classmethod
    def entries(cls, body: str) -> list[dict]:
        return cls._tree(body).entries()

    @staticmethod
    def _tree(body: str) -> _HeadingTree:
        tree = _HeadingTree()
        for line in body.splitlines():
            tree.take(line)
        return tree
