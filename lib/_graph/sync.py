from __future__ import annotations

from pathlib import Path
from typing import Protocol

import vault
from references import CitationEdge, CitationParser, CitedEntry, CorpusOnlyReader, HeldWorks, NoteEdges, UnheldEntries

from _graph.registry import UnheldRegistry
from _graph.store import CitationRow, GraphStore, held_key


class CentroidSource(Protocol):
    def centroid(self, basename: str) -> list[float] | None: ...


class NoteStamp:
    @staticmethod
    def of(path: Path) -> tuple[int, int]:
        status = path.stat()
        return status.st_size, status.st_mtime_ns


class GraphSync:
    def __init__(self, store: GraphStore, held: HeldWorks, parser: CitationParser, centroids: CentroidSource) -> None:
        self._store = store
        self._held = held
        self._unheld = UnheldEntries(held, parser, CorpusOnlyReader())
        self._registry = UnheldRegistry(store, parser)
        self._centroids = centroids

    def run(self, basenames: list[str] | None = None) -> dict:
        current = {vault.basename_of(path): path for path in vault.list_corpus_files()}
        stored = self._store.stamps()
        removed = [basename for basename in stored if basename not in current]
        for basename in removed:
            self._store.forget_note(basename)
        changed = [basename for basename in self._wanted(current, basenames)
                   if NoteStamp.of(current[basename]) != stored.get(basename)]
        for basename in changed:
            self._resync(basename, current[basename])
        return {"synced": len(changed), "removed": len(removed), "notes": len(current)}

    @staticmethod
    def _wanted(current: dict[str, Path], basenames: list[str] | None) -> list[str]:
        if basenames is None:
            return list(current)
        return [vault.nfc(basename) for basename in basenames if vault.nfc(basename) in current]

    def _resync(self, basename: str, path: Path) -> None:
        rows = self._held_rows(path) + self._unheld_rows(basename)
        self._store.replace_note(basename, NoteStamp.of(path), rows)
        self._store.set_centroid(basename, self._centroids.centroid(basename))

    @staticmethod
    def _held_rows(path: Path) -> list[CitationRow]:
        return [GraphSync._held_row(edge) for edge in NoteEdges(path).edges() if vault.held_note_exists(edge.cited)]

    @staticmethod
    def _held_row(edge: CitationEdge) -> CitationRow:
        return CitationRow(edge.citing, held_key(edge.cited), edge.folio, edge.file_page, edge.text)

    def _unheld_rows(self, basename: str) -> list[CitationRow]:
        if self._held.find(basename) is None:
            return []
        return [self._unheld_row(entry) for entry in self._unheld.of(basename).entries]

    def _unheld_row(self, entry: CitedEntry) -> CitationRow:
        row = self._registry.row_for(entry)
        return CitationRow(entry.locator.basename, row.key, entry.locator.folio, entry.locator.file_page, entry.text)
