from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

import vault as vault_lib

from .chroma import EmbeddingStore, RecordedModel
from .chunking import Child, ParentChildChunker
from .documents import FileStamp, IndexedDocument, UnreadableNote
from .fulltext import FullTextStore, ManifestRecord
from .search import SearchIndex


class SyncProgress:
    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stderr

    def changed(self, basename: str, children: int, embedded: int) -> None:
        self._line(f"{basename}: {children} children, {embedded} embedded")

    def unchanged(self, basename: str) -> None:
        self._line(f"{basename}: unchanged")

    def pruned(self, basename: str) -> None:
        self._line(f"{basename}: pruned")

    def unreadable(self, basename: str) -> None:
        self._line(f"{basename}: unreadable, skipped")

    def _line(self, text: str) -> None:
        print(text, file=self._stream, flush=True)


class _SyncReport:
    def __init__(self) -> None:
        self._changed: list[str] = []
        self._skipped: list[str] = []
        self._pruned: list[str] = []
        self._unreadable: list[dict] = []
        self._embedded_chunks = 0

    def changed(self, basename: str, embedded: int) -> None:
        self._changed.append(basename)
        self._embedded_chunks += embedded

    def skipped(self, basename: str) -> None:
        self._skipped.append(basename)

    def pruned(self, basename: str) -> None:
        self._pruned.append(basename)

    def unreadable(self, basename: str, error: UnreadableNote) -> None:
        self._unreadable.append({"basename": basename, "error": str(error)})

    def as_dict(self) -> dict:
        return {"changed": list(self._changed), "skipped": list(self._skipped), "pruned": list(self._pruned),
                "unreadable": list(self._unreadable), "embedded_chunks": self._embedded_chunks}


class _VectorLedger:
    def __init__(self, embeddings: EmbeddingStore) -> None:
        self._embeddings = embeddings
        self._held: set[str] | None = None

    def unembedded(self, children: list[Child]) -> list[Child]:
        return [child for child in children if child.chunk_id not in self._known()]

    def holds_all(self, chunk_ids: list[str]) -> bool:
        return self._known().issuperset(chunk_ids)

    def add(self, children: list[Child], vectors: list[list[float]]) -> None:
        self._embeddings.add(children, vectors)
        self._known().update(child.chunk_id for child in children)

    def delete(self, chunk_ids: list[str]) -> None:
        self._embeddings.delete(chunk_ids)
        self._known().difference_update(chunk_ids)

    def clear(self) -> None:
        self._embeddings.clear()
        self._held = set()

    def _known(self) -> set[str]:
        if self._held is None:
            self._held = self._embeddings.ids()
        return self._held


class _UnchangedDocuments:
    def __init__(self, fulltext: FullTextStore, chunker: ParentChildChunker, model: str) -> None:
        self._fulltext = fulltext
        self._chunker = chunker
        self._model = model

    def holds(self, basename: str, stamp: FileStamp) -> bool:
        row = self._fulltext.manifest_row(basename)
        if row is None or row.record.embedding_model != self._model:
            return False
        return row.record.is_stamped(stamp, self._chunker.document_hash_prefix)


class StoreSync:
    def __init__(self, index: SearchIndex | None = None, chunker: ParentChildChunker | None = None,
                 progress: SyncProgress | None = None) -> None:
        stores = index or SearchIndex.on_this_machine()
        self._documents = stores.documents
        self._fulltext = stores.fulltext
        self._embedder = stores.embedder
        self._embeddings = stores.embeddings
        self._chunker = chunker or ParentChildChunker()
        self._progress = progress or SyncProgress()
        self._ledger = _VectorLedger(self._embeddings)
        self._unchanged = _UnchangedDocuments(self._fulltext, self._chunker, self._embedder.model)
        self._report = _SyncReport()

    def run(self) -> None:
        self._require_the_recorded_model()
        paths = self._documents.paths()
        for path in paths:
            self._sync_one(path)
        self._prune({vault_lib.basename_of(path) for path in paths})

    def rebuild(self) -> None:
        self._fulltext.clear()
        self._ledger.clear()
        self.run()

    def report(self) -> dict:
        return self._report.as_dict()

    def _require_the_recorded_model(self) -> None:
        RecordedModel(self._embeddings.recorded_model(), self._embedder.model).require_agreement()

    def _sync_one(self, path: Path) -> None:
        basename = vault_lib.basename_of(path)
        if self._unchanged.holds(basename, FileStamp.of(path)) and self._vectors_held(basename):
            self._skip(basename)
            return
        self._sync_changed(basename, path)

    def _sync_changed(self, basename: str, path: Path) -> None:
        try:
            document = self._documents.loaded(path)
        except UnreadableNote as error:
            self._report.unreadable(basename, error)
            self._progress.unreadable(basename)
            return
        self._sync_loaded(document)

    def _sync_loaded(self, document: IndexedDocument) -> None:
        record = self._record(document)
        unchanged = self._fulltext.document_hash(document.basename) == record.document_hash
        if unchanged and self._vectors_held(document.basename):
            self._fulltext.restamp_document(document.basename, record)
            self._skip(document.basename)
            return
        self._write(document, record)

    def _write(self, document: IndexedDocument, record: ManifestRecord) -> None:
        chunked = self._chunker.chunked(document)
        children = list(chunked.children)
        held = set(self._fulltext.chunk_ids_of(document.basename))
        new = self._ledger.unembedded(children)
        self._embed(new)
        self._drop_stale_vectors(held, children)
        self._fulltext.replace_document(document.basename, chunked, record)
        self._report.changed(document.basename, len(new))
        self._progress.changed(document.basename, len(children), len(new))

    def _vectors_held(self, basename: str) -> bool:
        return self._ledger.holds_all(self._fulltext.chunk_ids_of(basename))

    def _embed(self, new: list[Child]) -> None:
        if new:
            self._ledger.add(new, self._embedder.embed([child.embedded_text for child in new]))

    def _drop_stale_vectors(self, held: set[str], children: list[Child]) -> None:
        self._ledger.delete(sorted(held - {child.chunk_id for child in children}))

    def _record(self, document: IndexedDocument) -> ManifestRecord:
        return ManifestRecord(self._chunker.document_hash(document), self._embedder.model, document.stamp)

    def _skip(self, basename: str) -> None:
        self._report.skipped(basename)
        self._progress.unchanged(basename)

    def _prune(self, present: set[str]) -> None:
        for basename in self._fulltext.manifest_basenames():
            if basename not in present:
                self._drop(basename)

    def _drop(self, basename: str) -> None:
        self._ledger.delete(self._fulltext.chunk_ids_of(basename))
        self._fulltext.remove_document(basename)
        self._report.pruned(basename)
        self._progress.pruned(basename)
