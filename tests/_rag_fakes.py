from __future__ import annotations

import hashlib
import math
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _rag.chunking import Child
from _rag.embedding import EmbeddingUnavailable
from _rag.fulltext import FullTextStore
from _rag.reranking import RerankerUnavailable
from _vaults import TempVault

VECTOR_DIMENSIONS = 8


def hashed_vector(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [byte / 255.0 for byte in digest[:VECTOR_DIMENSIONS]]


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norms = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norms if norms else 0.0


FAKE_MODEL = "fake-embedding"


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]] | None = None, failing: bool = False,
                 model: str = FAKE_MODEL) -> None:
        self._vectors = vectors or {}
        self._failing = failing
        self._model = model
        self.batches: list[list[str]] = []

    @property
    def model(self) -> str:
        return self._model

    def embed_query(self, query: str) -> list[float]:
        [vector] = self.embed([query])
        return vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._failing:
            raise EmbeddingUnavailable("fake embedder refused")
        self.batches.append(list(texts))
        return [self._vectors.get(text) or hashed_vector(text) for text in texts]

    @property
    def embedded_texts(self) -> list[str]:
        return [text for batch in self.batches for text in batch]


class FakeEmbeddingStore:
    def __init__(self, model: str | None = None) -> None:
        self._vectors: dict[str, list[float]] = {}
        self._model = model

    def recorded_model(self) -> str | None:
        return self._model

    def present(self) -> bool:
        return bool(self._vectors)

    def count(self) -> int:
        return len(self._vectors)

    def ids(self) -> set[str]:
        return set(self._vectors)

    def add(self, children: list[Child], vectors: list[list[float]]) -> None:
        for child, vector in zip(children, vectors):
            self._vectors[child.chunk_id] = vector

    def delete(self, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self._vectors.pop(chunk_id, None)

    def nearest(self, vector: list[float], limit: int) -> list[str]:
        ranked = sorted(self._vectors, key=lambda chunk_id: cosine(vector, self._vectors[chunk_id]), reverse=True)
        return ranked[:limit]

    def clear(self) -> None:
        self._vectors.clear()
        self._model = None


class FakeReranker:
    def __init__(self, scores_by_fragment: dict[str, float] | None = None, cause: str | None = None) -> None:
        self._scores = scores_by_fragment or {}
        self._cause = cause
        self.queries: list[str] = []

    def unavailable_cause(self) -> str | None:
        return self._cause

    def scores(self, query: str, passages: list[str]) -> list[float]:
        if self._cause is not None:
            raise RerankerUnavailable(self._cause)
        self.queries.append(query)
        return [max((score for fragment, score in self._scores.items() if fragment in passage), default=0.0)
                for passage in passages]


def temp_directory(test: unittest.TestCase) -> Path:
    directory = tempfile.TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    return Path(directory.name)


class CorpusStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_vault = TempVault("CORPUS_DIR").activate()
        self.addCleanup(self.temp_vault.discard)
        self.fulltext = FullTextStore(temp_directory(self))
