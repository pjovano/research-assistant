from __future__ import annotations

import re
from dataclasses import dataclass

import vault
from page_marker import PageMarker
from _references.entries import EntryParser, ReferenceEntry
from _references.notes import DEFINITION_RE, NoteLines
from _references.records import ReferenceExtractor
from _references.zones import CachedZone
from _references.works import LibraryWork

SOURCE_CORPUS = "corpus"
SOURCE_PDF = "pdf"

_SPACING_RE = re.compile(r"\s+")
_WIKILINK_OPEN = "[["


@dataclass(frozen=True)
class Locator:
    basename: str
    folio: str | None
    file_page: int | None
    text: str

    def as_dict(self) -> dict:
        return {"basename": self.basename, "folio": self.folio, "file_page": self.file_page, "text": self.text}


@dataclass(frozen=True)
class CitedEntry:
    surnames: tuple[str, ...]
    year: str | None
    locator: Locator

    @property
    def text(self) -> str:
        return self.locator.text


@dataclass(frozen=True)
class ReferenceReading:
    source: str
    entries: list[CitedEntry]


class MarkedLines:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def located(self, indices: list[int]) -> list[tuple[PageMarker | None, str]]:
        wanted, current, found = set(indices), None, []
        for index, line in enumerate(self._lines):
            marker = PageMarker.parsed(line)
            if marker is not None:
                current = marker
                continue
            if index in wanted:
                found.append((current, self._without_markers(line)))
            current = self._last_inline(line, current)
        return found

    @staticmethod
    def page_of(marker: PageMarker | None) -> tuple[str | None, int | None]:
        if marker is None:
            return None, None
        return marker.folio, marker.file_page

    @staticmethod
    def _without_markers(line: str) -> str:
        return _SPACING_RE.sub(" ", PageMarker.stripped(line)).strip()

    @staticmethod
    def _last_inline(line: str, current: PageMarker | None) -> PageMarker | None:
        inline = PageMarker.inline(line)
        return inline[-1] if inline else current


class CorpusEntries:
    def __init__(self, work: LibraryWork) -> None:
        self._work = work
        self._parser = EntryParser()

    def entries(self) -> list[CitedEntry]:
        path = vault.corpus_path(self._work.basename)
        if not path.exists():
            return []
        _frontmatter, body = vault.read_frontmatter(path)
        note = NoteLines(body)
        return [entry for marker, line in MarkedLines(note.lines).located(note.entry_indices())
                for entry in self._parsed(marker, line)]

    def _parsed(self, marker: PageMarker | None, line: str) -> list[CitedEntry]:
        if _WIKILINK_OPEN in line:
            return []
        match = DEFINITION_RE.match(line)
        text = match.group(2) if match else line
        return [self._entry(marker, parsed) for parsed in self._parser.parse(text)]

    def _entry(self, marker: PageMarker | None, parsed: ReferenceEntry) -> CitedEntry:
        folio, file_page = MarkedLines.page_of(marker)
        return CitedEntry(parsed.surnames, parsed.year, Locator(self._work.basename, folio, file_page, parsed.raw))


class PdfEntries:
    def __init__(self, work: LibraryWork) -> None:
        self._work = work

    def entries(self) -> list[CitedEntry]:
        pdf_path = vault.pdf_path(self._work.basename)
        record = ReferenceExtractor().of_zone(pdf_path.stem, CachedZone(pdf_path).locate())
        return [CitedEntry(entry.surnames, entry.year,
                           Locator(self._work.basename, None, record.first_page, entry.raw))
                for entry in record.entries]


class ReferenceReader:
    def read(self, work: LibraryWork) -> ReferenceReading:
        from_corpus = CorpusEntries(work).entries()
        if from_corpus:
            return ReferenceReading(SOURCE_CORPUS, from_corpus)
        return ReferenceReading(SOURCE_PDF, PdfEntries(work).entries())


class CorpusOnlyReader:
    def read(self, work: LibraryWork) -> ReferenceReading:
        return ReferenceReading(SOURCE_CORPUS, CorpusEntries(work).entries())
