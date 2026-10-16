from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import vault as vault_lib

from .chroma import EmbeddingStore
from .chunking import embedded_text
from .documents import FileStamp, IndexableDocuments
from .embedding import EmbeddingUnavailable, OllamaEmbedder
from .fulltext import CONTEXT, TEXT, FullTextStore, ManifestRow
from .fusion import ReciprocalRankFusion
from .reranking import LlamaReranker, RerankerUnavailable
from .results import ResultAssembly

DEFAULT_RESULTS = 8
CANDIDATES_PER_RANKING = 100
RERANK_CANDIDATES = 50
QUERY_JOIN = " "
STALE_JOIN = ", "

_VECTOR_WARNING = ("semantic (vector) search was unavailable — these results are "
                   "keyword-only, so a passage phrased differently from the query "
                   "may have been missed. Cause: {cause}")
_RERANK_WARNING = "reranker unavailable: {cause}; results are the fused hybrid ordering"
_STALE_WARNING = ("stale: {basenames} — changed since it was indexed, or never indexed; "
                  "run `search.py sync`")
_RERANKER_USED = "used: the fused candidates were reordered by the reranker"

Scored = list[tuple[str, float]]


class _Queries:
    def __init__(self, given: str | list[str]) -> None:
        self._texts = [given] if isinstance(given, str) else list(given)

    @property
    def texts(self) -> list[str]:
        return self._texts

    @property
    def joined(self) -> str:
        return QUERY_JOIN.join(self._texts)


class _Notes:
    def __init__(self) -> None:
        self._warnings: list[dict] = []
        self._reranked = False

    def warn(self, message: str) -> None:
        self._warnings.append({"warning": message})

    def mark_reranked(self) -> None:
        self._reranked = True

    def entries(self) -> list[dict]:
        reranker = [{"reranker": _RERANKER_USED}] if self._reranked else []
        return reranker + list(self._warnings)


class _CorpusStaleness:
    def __init__(self, documents: IndexableDocuments, fulltext: FullTextStore) -> None:
        self._documents = documents
        self._fulltext = fulltext
        self._listing_key: tuple | None = None
        self._stamps: dict[str, FileStamp] = {}

    def basenames(self) -> list[str]:
        rows = {row.basename: row for row in self._fulltext.manifest_rows()}
        stamps = self._stamps_under(self._listing_key_now(rows))
        return [basename for basename, stamp in stamps.items() if self._differs(stamp, rows.get(basename))]

    def _stamps_under(self, key: tuple) -> dict[str, FileStamp]:
        if key != self._listing_key:
            named = {vault_lib.basename_of(path): path for path in self._documents.paths()}
            self._stamps = {basename: FileStamp.of(path) for basename, path in named.items()}
            self._listing_key = key
        return self._stamps

    def _listing_key_now(self, rows: dict[str, ManifestRow]) -> tuple:
        directory_mtimes = tuple(self._mtime_of(directory) for directory in self._documents.directories)
        return directory_mtimes, frozenset((basename, row.record.stamp) for basename, row in rows.items())

    @staticmethod
    def _mtime_of(directory: Path) -> int | None:
        return directory.stat().st_mtime_ns if directory.exists() else None

    @staticmethod
    def _differs(stamp: FileStamp, row: ManifestRow | None) -> bool:
        return row is None or row.record.stamp != stamp


@dataclass(frozen=True)
class SearchIndex:
    fulltext: FullTextStore
    embeddings: EmbeddingStore
    embedder: OllamaEmbedder
    documents: IndexableDocuments

    @staticmethod
    def on_this_machine() -> "SearchIndex":
        return SearchIndex(FullTextStore(), EmbeddingStore(), OllamaEmbedder(), IndexableDocuments())


class HybridSearch:
    def __init__(self, index: SearchIndex, reranker: LlamaReranker | None = None) -> None:
        self._fulltext = index.fulltext
        self._embeddings = index.embeddings
        self._embedder = index.embedder
        self._reranker = reranker
        self._fusion = ReciprocalRankFusion()
        self._staleness = _CorpusStaleness(index.documents, index.fulltext)

    def results(self, query: str | list[str], k: int = DEFAULT_RESULTS) -> list[dict]:
        queries = _Queries(query)
        notes = _Notes()
        fused = self._fusion.fused(self._rankings(queries, notes))
        entries = ResultAssembly(self._fulltext, k).entries(self._ordered(queries, fused, notes))
        self._note_staleness(notes)
        return entries + notes.entries()

    def _rankings(self, queries: _Queries, notes: _Notes) -> list[list[str]]:
        keyword = [self._fulltext.bm25_ranked(text, CANDIDATES_PER_RANKING) for text in queries.texts]
        return keyword + self._vector_rankings(queries, notes)

    def _vector_rankings(self, queries: _Queries, notes: _Notes) -> list[list[str]]:
        try:
            vectors = [self._embedder.embed_query(text) for text in queries.texts]
        except EmbeddingUnavailable as error:
            notes.warn(_VECTOR_WARNING.format(cause=error))
            return []
        return [self._embeddings.nearest(vector, CANDIDATES_PER_RANKING) for vector in vectors]

    def _note_staleness(self, notes: _Notes) -> None:
        stale = self._staleness.basenames()
        if stale:
            notes.warn(_STALE_WARNING.format(basenames=STALE_JOIN.join(stale)))

    def _ordered(self, queries: _Queries, fused: Scored, notes: _Notes) -> Scored:
        if self._reranker is None or not fused:
            return fused
        try:
            reranked = self._reranked(queries.joined, fused[:RERANK_CANDIDATES])
        except RerankerUnavailable as error:
            notes.warn(_RERANK_WARNING.format(cause=error))
            return fused
        notes.mark_reranked()
        return reranked

    def _reranked(self, query: str, candidates: Scored) -> Scored:
        candidate_ids = [chunk_id for chunk_id, _ in candidates]
        children = self._fulltext.children_by_id(candidate_ids)
        chunk_ids = [chunk_id for chunk_id in candidate_ids if chunk_id in children]
        scores = self._reranker.scores(query, self._passages(children, chunk_ids))
        return sorted(zip(chunk_ids, scores), key=lambda pair: pair[1], reverse=True)

    @staticmethod
    def _passages(children: dict[str, dict], chunk_ids: list[str]) -> list[str]:
        return [embedded_text(children[chunk_id][CONTEXT], children[chunk_id][TEXT]) for chunk_id in chunk_ids]
