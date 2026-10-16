from __future__ import annotations

import contextlib
import re
import shutil
from collections.abc import Iterator, Sequence
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _ports.compute import Cost, Segment, Turn
from _ports.host import Device
from _rag.chunking import ChunkedDocument
from _rag.fulltext import ManifestRecord, ManifestRow

FAKE_CONFLICT_COPY = re.compile(r" \d+(\.[^.]+)$")
FULLTEXT_TABLES = ("parents", "children", "manifest")
WORD = re.compile(r"[^\W_]+", re.UNICODE)


class FakeAccelerator:
    def __init__(self, device: Device = "cpu", failure: str | None = None) -> None:
        self._device = device
        self._failure = failure

    def device(self) -> Device:
        return self._device

    def reachable(self) -> str | None:
        return self._failure


class FakeTrash:
    def __init__(self, bin_directory: Path) -> None:
        self._bin = bin_directory

    def discard(self, path: Path) -> None:
        self._bin.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(self._bin / path.name))


class FakeSyncedFolder:
    def __init__(self, placeholders: frozenset[Path] = frozenset()) -> None:
        self._placeholders = placeholders

    def conflict_copies(self, directory: Path) -> list[Path]:
        return sorted(path for path in directory.iterdir() if FAKE_CONFLICT_COPY.search(path.name))

    def not_downloaded(self, path: Path) -> bool:
        return path in self._placeholders


class FakeLocations:
    def __init__(self, home: Path) -> None:
        self._home = home

    @property
    def vault_root(self) -> Path:
        return self._home / "Documents"

    @property
    def inbox(self) -> Path:
        return self._home / "inbox"

    @property
    def state_dir(self) -> Path:
        return self._home / "state"

    @property
    def rag_dir(self) -> Path:
        return self.state_dir / "rag"


class FakeFullTextStore:
    def __init__(self) -> None:
        self._documents: dict[str, tuple[ChunkedDocument, ManifestRecord]] = {}

    def present(self) -> bool:
        return bool(self._documents)

    def manifest_row(self, basename: str) -> ManifestRow | None:
        if basename not in self._documents:
            return None
        chunked, record = self._documents[basename]
        return ManifestRow(basename, chunked.chunk_ids, record)

    def manifest_rows(self) -> list[ManifestRow]:
        return [self.manifest_row(basename) for basename in self.manifest_basenames()]

    def document_hash(self, basename: str) -> str | None:
        row = self.manifest_row(basename)
        return None if row is None else row.record.document_hash

    def chunk_ids_of(self, basename: str) -> list[str]:
        row = self.manifest_row(basename)
        return [] if row is None else row.chunk_ids

    def manifest_basenames(self) -> list[str]:
        return sorted(self._documents)

    def child_ids(self) -> set[str]:
        return {child["chunk_id"] for child in self._all_children()}

    def counts(self) -> dict[str, int]:
        parents = sum(len(chunked.parents) for chunked, _record in self._documents.values())
        return dict(zip(FULLTEXT_TABLES, (parents, len(self._all_children()), len(self._documents))))

    def replace_document(self, basename: str, chunked: ChunkedDocument, record: ManifestRecord) -> None:
        self._documents[basename] = (chunked, record)

    def restamp_document(self, basename: str, record: ManifestRecord) -> None:
        chunked, _old = self._documents[basename]
        self._documents[basename] = (chunked, record)

    def remove_document(self, basename: str) -> None:
        self._documents.pop(basename, None)

    def clear(self) -> None:
        self._documents.clear()

    def bm25_ranked(self, query: str, limit: int) -> list[str]:
        terms = set(WORD.findall(query.lower()))
        matched = [(len(terms & set(WORD.findall(child["text"].lower()))), child["chunk_id"])
                   for child in self._all_children()]
        return [chunk_id for hits, chunk_id in sorted(matched, key=lambda pair: -pair[0]) if hits][:limit]

    def children(self, chunk_ids: list[str]) -> list[dict]:
        return [child for child in self._all_children() if child["chunk_id"] in chunk_ids]

    def children_by_id(self, chunk_ids: list[str]) -> dict[str, dict]:
        return {child["chunk_id"]: child for child in self.children(chunk_ids)}

    def parents(self, parent_ids: list[str]) -> list[dict]:
        rows = [vars(parent) for chunked, _record in self._documents.values() for parent in chunked.parents]
        return [dict(row) for row in rows if row["parent_id"] in parent_ids]

    def _all_children(self) -> list[dict]:
        return [{name: value for name, value in vars(child).items() if name != "embedded_text"}
                for chunked, _record in self._documents.values() for child in chunked.children]


class FakeLayoutEngine:
    def __init__(self, page_count: int = 1, pixel_pages: int = 0) -> None:
        self._cost = Cost(pixel_pages, page_count)
        self.conversions: list[tuple[Path, str]] = []

    def convert(self, pdf: Path, file_pages: list[int] | None, mode: str) -> dict:
        self.conversions.append((pdf, mode))
        pages = file_pages or list(range(1, int(self._cost.pages) + 1))
        return {"children": [{"page": page} for page in pages]}

    def cost(self, pdf: Path) -> Cost:
        return self._cost

    @contextlib.contextmanager
    def session(self) -> Iterator[None]:
        yield


class FakeLineRecognizer:
    def __init__(self, texts: dict[object, str] | None = None) -> None:
        self._texts = texts or {}

    def read(self, images: Sequence[object]) -> list[str]:
        return [self._texts.get(image, "") for image in images]


class FakeTranscriber:
    def __init__(self, segments: list[Segment]) -> None:
        self._segments = segments

    def segments(self, audio: Path, language: str | None) -> list[Segment]:
        return list(self._segments)


class FakeDiarizer:
    def __init__(self, turns: list[Turn]) -> None:
        self._turns = turns

    def turns(self, audio: Path) -> list[Turn]:
        return list(self._turns)
