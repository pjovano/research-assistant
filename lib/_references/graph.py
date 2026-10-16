from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import vault
from notation import blanked_notation
from page_marker import PageMarker
from _references.notes import NoteLines
from _references.reading import MarkedLines


@dataclass(frozen=True)
class CitationEdge:
    citing: str
    cited: str
    folio: str | None
    file_page: int | None
    text: str = ""

    def toward_cited(self) -> dict:
        return self._toward(self.cited)

    def toward_citing(self) -> dict:
        return self._toward(self.citing)

    def _toward(self, basename: str) -> dict:
        return {"basename": basename, "folio": self.folio, "file_page": self.file_page}


class NoteEdges:
    def __init__(self, path: Path) -> None:
        self._path = path

    def edges(self) -> list[CitationEdge]:
        _frontmatter, body = vault.read_frontmatter(self._path)
        note = NoteLines(blanked_notation(body))
        located = MarkedLines(note.lines).located(note.entry_indices())
        return [self._edge(marker, line, link.group("target"))
                for marker, line in located for link in vault.WIKILINK_RE.finditer(line)]

    def _edge(self, marker: PageMarker | None, line: str, target: str) -> CitationEdge:
        folio, file_page = MarkedLines.page_of(marker)
        return CitationEdge(vault.basename_of(self._path), vault.nfc(target.strip()), folio, file_page, line)


class NoteEdgeCache:
    def __init__(self) -> None:
        self._by_path: dict[str, tuple[tuple[int, int], list[CitationEdge]]] = {}

    def edges(self, path: Path) -> list[CitationEdge]:
        stamp, cached = self._stamp(path), self._by_path.get(str(path))
        if cached is None or cached[0] != stamp:
            cached = (stamp, NoteEdges(path).edges())
            self._by_path[str(path)] = cached
        return list(cached[1])

    @staticmethod
    def _stamp(path: Path) -> tuple[int, int]:
        status = path.stat()
        return status.st_size, status.st_mtime_ns


class CitationGraph:
    def __init__(self) -> None:
        self._cache = NoteEdgeCache()

    def cites(self, basename: str) -> dict:
        path = vault.corpus_path(basename)
        if not path.exists():
            raise LookupError(f"'{basename}' has no corpus file in {vault.CORPUS_DIR}")
        return {"basename": basename, "cites": [edge.toward_cited() for edge in self._cache.edges(path)]}

    def cited_by(self, basename: str) -> dict:
        if not vault.held_note_exists(basename):
            raise LookupError(f"'{basename}' has no corpus file in {vault.CORPUS_DIR} "
                              f"and no transcript in {vault.TRANSCRIPTS_DIR}")
        cited = vault.nfc(basename)
        citing = [edge.toward_citing() for path in vault.list_corpus_files()
                  for edge in self._cache.edges(path) if edge.cited == cited]
        return {"basename": basename, "cited_by": citing}
