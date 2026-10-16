from __future__ import annotations

from pathlib import Path

import vault as vault_lib

from .chunking import Child
from .settings import MachineSettings

COLLECTION_NAME = "vault"
EMBEDDING_MODEL_METADATA = "embedding_model"
REBUILD_INSTRUCTION = "run `search.py sync --rebuild`"
_COLLECTION_CONFIGURATION = {"hnsw": {"space": "cosine"}}


class EmbeddingModelMismatch(RuntimeError):
    pass


class RecordedModel:
    def __init__(self, recorded: str | None, configured: str) -> None:
        self._recorded = recorded
        self._configured = configured

    def disagreement(self) -> str | None:
        if self._recorded is None or self._recorded == self._configured:
            return None
        return (f"the embedding store holds vectors from {self._recorded}, "
                f"{self._configured} is configured -- {REBUILD_INSTRUCTION}")

    def require_agreement(self) -> None:
        disagreement = self.disagreement()
        if disagreement is not None:
            raise EmbeddingModelMismatch(disagreement)


class EmbeddingStore:
    def __init__(self, directory: Path | None = None, settings: MachineSettings | None = None) -> None:
        self._directory = directory or vault_lib.CHROMA_DIR
        self._settings = settings or MachineSettings()
        self._held_client = None
        self._held_collection = None

    def present(self) -> bool:
        return self._collection() is not None

    def count(self) -> int:
        collection = self._collection()
        return 0 if collection is None else collection.count()

    def ids(self) -> set[str]:
        collection = self._collection()
        return set() if collection is None else set(collection.get(include=[])["ids"])

    def recorded_model(self) -> str | None:
        collection = self._collection()
        return None if collection is None else _recorded_model(collection)

    def add(self, children: list[Child], vectors: list[list[float]]) -> None:
        if not children:
            return
        collection = self._opened_collection()
        self._require_the_configured_model(collection)
        _Upsert(self._client().get_max_batch_size()).into(collection, children, vectors)

    def delete(self, chunk_ids: list[str]) -> None:
        if chunk_ids:
            self._opened_collection().delete(ids=list(chunk_ids))

    def vectors_of(self, basename: str) -> list[list[float]]:
        collection = self._collection()
        if collection is None:
            return []
        found = collection.get(where={"basename": basename}, include=["embeddings"])["embeddings"]
        return [list(map(float, vector)) for vector in found]

    def nearest(self, vector: list[float], limit: int) -> list[str]:
        held = self.count()
        if held == 0:
            return []
        return self._collection().query(query_embeddings=[vector], n_results=min(limit, held), include=[])["ids"][0]

    def clear(self) -> None:
        if self.present():
            self._client().delete_collection(COLLECTION_NAME)
        self._held_collection = None

    def release(self) -> None:
        if self._held_client is None:
            return
        from chromadb.api.client import SharedSystemClient
        self._held_collection = None
        self._held_client = None
        SharedSystemClient.clear_system_cache()

    def _require_the_configured_model(self, collection) -> None:
        RecordedModel(_recorded_model(collection), self._settings.embedding_model).require_agreement()

    def _opened_collection(self):
        if self._held_collection is None:
            self._held_collection = self._client().get_or_create_collection(
                COLLECTION_NAME, metadata={EMBEDDING_MODEL_METADATA: self._settings.embedding_model},
                configuration=_COLLECTION_CONFIGURATION)
        return self._held_collection

    def _collection(self):
        if self._held_collection is None and self._directory.exists():
            self._held_collection = self._found_collection()
        return self._held_collection

    def _found_collection(self):
        from chromadb.errors import NotFoundError
        try:
            return self._client().get_collection(COLLECTION_NAME)
        except NotFoundError:
            return None

    def _client(self):
        if self._held_client is None:
            import chromadb
            from chromadb.config import Settings
            self._held_client = chromadb.PersistentClient(path=str(self._directory),
                                                          settings=Settings(anonymized_telemetry=False))
        return self._held_client


class _Upsert:
    def __init__(self, batch_size: int) -> None:
        self._batch_size = batch_size

    def into(self, collection, children: list[Child], vectors: list[list[float]]) -> None:
        for start in range(0, len(children), self._batch_size):
            end = start + self._batch_size
            batch = children[start:end]
            collection.upsert(ids=[child.chunk_id for child in batch],
                              embeddings=vectors[start:end],
                              documents=[child.embedded_text for child in batch],
                              metadatas=[{"basename": child.basename} for child in batch])


def _recorded_model(collection) -> str | None:
    return (collection.metadata or {}).get(EMBEDDING_MODEL_METADATA)
