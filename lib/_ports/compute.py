from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

MODE_TEXT_LAYER = "text-layer"
MODE_FORCED_OCR = "forced-ocr"
LAYOUT_MODES = (MODE_TEXT_LAYER, MODE_FORCED_OCR)
Vector = list[float]
StoredRow = dict[str, Any]


@dataclass(frozen=True)
class Cost:
    pixel_pages: float
    pages: float


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class Turn:
    start_ms: int
    end_ms: int
    speaker: str


class Chunk(Protocol):
    @property
    def chunk_id(self) -> str: ...


class ChunkedText(Protocol):
    @property
    def parents(self) -> Sequence[Any]: ...

    @property
    def children(self) -> Sequence[Chunk]: ...

    @property
    def chunk_ids(self) -> list[str]: ...


class Embedder(Protocol):
    @property
    def model(self) -> str: ...

    def embed(self, texts: list[str]) -> list[Vector]: ...

    def embed_query(self, query: str) -> Vector: ...


class EmbeddingStore(Protocol):
    def recorded_model(self) -> str | None: ...

    def present(self) -> bool: ...

    def count(self) -> int: ...

    def ids(self) -> set[str]: ...

    def add(self, children: Sequence[Chunk], vectors: list[Vector]) -> None: ...

    def delete(self, chunk_ids: list[str]) -> None: ...

    def nearest(self, vector: Vector, limit: int) -> list[str]: ...

    def clear(self) -> None: ...


class FullTextStore(Protocol):
    def present(self) -> bool: ...

    def manifest_row(self, basename: str) -> Any | None: ...

    def manifest_rows(self) -> list[Any]: ...

    def document_hash(self, basename: str) -> str | None: ...

    def chunk_ids_of(self, basename: str) -> list[str]: ...

    def manifest_basenames(self) -> list[str]: ...

    def child_ids(self) -> set[str]: ...

    def counts(self) -> dict[str, int]: ...

    def replace_document(self, basename: str, chunked: ChunkedText, record: Any) -> None: ...

    def restamp_document(self, basename: str, record: Any) -> None: ...

    def remove_document(self, basename: str) -> None: ...

    def clear(self) -> None: ...

    def bm25_ranked(self, query: str, limit: int) -> list[str]: ...

    def children(self, chunk_ids: list[str]) -> list[StoredRow]: ...

    def children_by_id(self, chunk_ids: list[str]) -> dict[str, StoredRow]: ...

    def parents(self, parent_ids: list[str]) -> list[StoredRow]: ...


class Reranker(Protocol):
    def scores(self, query: str, passages: list[str]) -> list[float]: ...

    def unavailable_cause(self) -> str | None: ...

    def stop(self) -> None: ...


class LayoutEngine(Protocol):
    def convert(self, pdf: Path, file_pages: list[int] | None, mode: str) -> dict: ...

    def cost(self, pdf: Path) -> Cost: ...

    def session(self) -> AbstractContextManager[None]: ...


class LineRecognizer(Protocol):
    def read(self, images: Sequence[Any]) -> list[str]: ...


class Transcriber(Protocol):
    def segments(self, audio: Path, language: str | None) -> list[Segment]: ...


class Diarizer(Protocol):
    def turns(self, audio: Path) -> list[Turn]: ...


class CitationParser(Protocol):
    def parse(self, entry_text: str) -> Any: ...
