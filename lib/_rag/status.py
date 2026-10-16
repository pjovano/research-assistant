from __future__ import annotations

from pathlib import Path

import vault as vault_lib

from .chroma import REBUILD_INSTRUCTION, EmbeddingStore, RecordedModel
from .chunking import ParentChildChunker
from .documents import FileStamp
from .fulltext import PARENTS_TABLE, FullTextStore, ManifestRow
from .reranking import LlamaReranker
from .search import SearchIndex

_RERANKER_CONFIGURED = "configured; probed on the first query of the session"
_UNRECORDED_MODEL = "unrecorded"


class _StoredCounts:
    def __init__(self, fulltext: FullTextStore, embeddings: EmbeddingStore, rows: dict[str, ManifestRow]) -> None:
        self._manifest_ids = {chunk_id for row in rows.values() for chunk_id in row.chunk_ids}
        self._child_ids = fulltext.child_ids()
        self._parents = fulltext.counts()[PARENTS_TABLE]
        self._chroma_ids = embeddings.ids() if embeddings.present() else None

    def fields(self) -> dict:
        return {"chroma_chunk_count": None if self._chroma_ids is None else len(self._chroma_ids),
                "fulltext_child_count": len(self._child_ids),
                "fulltext_parent_count": self._parents,
                "manifest_chunk_count": len(self._manifest_ids)}

    def disagreement(self) -> str | None:
        held = set() if self._chroma_ids is None else self._chroma_ids
        if self._manifest_ids == self._child_ids == held:
            return None
        return (f"manifest holds {len(self._manifest_ids)} chunk ids, the full-text store {len(self._child_ids)}, "
                f"the embedding store {len(held)} -- {REBUILD_INSTRUCTION}")


class _RecordedModels:
    def __init__(self, configured: str, recorded: str | None) -> None:
        self._configured = configured
        self._recorded = recorded
        self._agreement = RecordedModel(recorded, configured)

    def fields(self) -> dict:
        return {"embedding_model": self._configured,
                "recorded_embedding_model": self._recorded or _UNRECORDED_MODEL}

    def disagreement(self) -> str | None:
        return self._agreement.disagreement()


class IndexStatus:
    def __init__(self, index: SearchIndex | None = None, reranker: LlamaReranker | None = None) -> None:
        self._index = index or SearchIndex.on_this_machine()
        self._reranker = reranker or LlamaReranker()
        self._held_chunker: ParentChildChunker | None = None

    def report(self) -> dict:
        named = {vault_lib.basename_of(path): path for path in self._index.documents.paths()}
        rows = {row.basename: row for row in self._index.fulltext.manifest_rows()}
        counts = _StoredCounts(self._index.fulltext, self._index.embeddings, rows)
        models = _RecordedModels(self._index.embedder.model, self._index.embeddings.recorded_model())
        problem = counts.disagreement() or models.disagreement()
        return {"corpus_files_indexable": len(named),
                "indexed_in_manifest": len(rows),
                "stale_or_new": [name for name, path in named.items() if self._is_stale(path, rows.get(name))],
                **counts.fields(), **models.fields(),
                "consistent": problem is None, "inconsistency": problem,
                "reranker": self._reranker_state()}

    def _is_stale(self, path: Path, row: ManifestRow | None) -> bool:
        if row is None:
            return True
        if row.record.is_stamped(FileStamp.of(path), self._chunker().document_hash_prefix):
            return False
        return row.record.document_hash != self._chunker().document_hash(self._index.documents.loaded(path))

    def _chunker(self) -> ParentChildChunker:
        if self._held_chunker is None:
            self._held_chunker = ParentChildChunker()
        return self._held_chunker

    def _reranker_state(self) -> str:
        cause = self._reranker.unavailable_cause()
        return _RERANKER_CONFIGURED if cause is None else f"unavailable: {cause}"
