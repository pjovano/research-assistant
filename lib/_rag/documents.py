from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

import vault as vault_lib

from .markdown import LINE_JOIN

UNSTAMPED = -1
_ENCODING = "utf-8"


@dataclass(frozen=True)
class FileStamp:
    size: int
    mtime_ns: int

    @staticmethod
    def of(path: Path) -> "FileStamp":
        status = path.stat()
        return FileStamp(status.st_size, status.st_mtime_ns)

    @staticmethod
    def unstamped() -> "FileStamp":
        return FileStamp(UNSTAMPED, UNSTAMPED)


@dataclass(frozen=True)
class IndexedDocument:
    basename: str
    path: Path
    meta: dict
    body: str
    content_hash: str = ""
    stamp: FileStamp = field(default_factory=FileStamp.unstamped)

    @property
    def key(self) -> str:
        return self.basename


class UnreadableNote(ValueError):
    pass


class _NoteFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._stamp = FileStamp.of(path)
        self._bytes = path.read_bytes()

    def document(self) -> IndexedDocument:
        meta, body = self._parsed_note()
        indexable = BibliographySection.removed_from(vault_lib.body_after_source_link(body))
        return IndexedDocument(vault_lib.basename_of(self._path), self._path, meta, indexable, self._content_hash(),
                               self._stamp)

    def _parsed_note(self) -> tuple[dict, str]:
        try:
            return vault_lib.parse_note(self._bytes.decode(_ENCODING))
        except (yaml.YAMLError, UnicodeDecodeError) as error:
            raise UnreadableNote(f"{self._path.name}: {error}") from error

    def _content_hash(self) -> str:
        return hashlib.sha256(self._bytes).hexdigest()


class IndexableDocuments:
    @property
    def directories(self) -> tuple[Path, ...]:
        return (vault_lib.CORPUS_DIR, vault_lib.TRANSCRIPTS_DIR)

    def paths(self) -> list[Path]:
        return vault_lib.list_held_notes()

    def loaded(self, path: Path) -> IndexedDocument:
        return _NoteFile(path).document()


class BibliographySection:
    @classmethod
    def removed_from(cls, body: str) -> str:
        lines = body.split(LINE_JOIN)
        return LINE_JOIN.join(cls._outside(lines, vault_lib.BibliographySpan(lines).all()))

    @staticmethod
    def _outside(lines: list[str], spans: list[tuple[int, int]]) -> list[str]:
        kept: list[str] = []
        position = 0
        for start, end in spans:
            kept.extend(lines[position:max(start, position)])
            position = max(position, end)
        kept.extend(lines[position:])
        return kept
