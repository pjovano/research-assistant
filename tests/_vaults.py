from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pymupdf
import vault

TEXT_ORIGIN = (72, 100)
DEFAULT_PAGES = 3
PATCHED_DIRS = ("INBOX_DIR", "LIBRARY_DIR", "VOLUMES_DIR")

_SUBDIRECTORIES = {
    "INBOX_DIR": "inbox",
    "LIBRARY_DIR": "library",
    "VOLUMES_DIR": "library/volumes",
    "BIBLIOGRAPHIES_DIR": "bibliographies",
    "CORPUS_DIR": "corpus",
    "TRANSCRIPTS_DIR": "corpus/talk transcripts",
    "SCRATCH_DIR": "scratch",
    "RAG_DIR": "rag",
    "WRITING_DIR": "writing",
}


class TempVault:
    ALWAYS_PATCHED = ("SCRATCH_DIR", "TRANSCRIPTS_DIR", "WRITING_DIR")

    def __init__(self, *directories: str) -> None:
        self._root = Path(tempfile.mkdtemp())
        self._directories = tuple(dict.fromkeys(directories + self.ALWAYS_PATCHED))
        self._saved = {name: getattr(vault, name) for name in self._directories}

    def activate(self) -> "TempVault":
        for name in self._directories:
            path = self._root / _SUBDIRECTORIES[name]
            path.mkdir(parents=True, exist_ok=True)
            setattr(vault, name, path)
        return self

    def discard(self) -> None:
        for name, value in self._saved.items():
            setattr(vault, name, value)
        shutil.rmtree(self._root, ignore_errors=True)

    def named(self, name: str) -> Path:
        return self._root / name

    @property
    def inbox(self) -> Path:
        return vault.INBOX_DIR

    @property
    def library(self) -> Path:
        return vault.LIBRARY_DIR

    @property
    def volumes(self) -> Path:
        return vault.VOLUMES_DIR

    @property
    def corpus(self) -> Path:
        return vault.CORPUS_DIR


class LinedPdf:
    LINE_PITCH = 14

    def __init__(self, path: Path, pages: list[list[str]], outline: list | None = None) -> None:
        self._path = path
        self._pages = pages
        self._outline = outline or []

    def write(self) -> Path:
        with pymupdf.open() as doc:
            for lines in self._pages:
                self._draw(doc.new_page(), lines)
            if self._outline:
                doc.set_toc(self._outline)
            doc.save(self._path)
        return self._path

    def _draw(self, page, lines: list[str]) -> None:
        left, top = TEXT_ORIGIN
        for number, line in enumerate(lines):
            page.insert_text((left, top + number * self.LINE_PITCH), line)


class TextPdf:
    def __init__(self, path: Path, pages: int = DEFAULT_PAGES, outline: list | None = None) -> None:
        self._path = path
        self._pages = pages
        self._outline = outline or []

    def write(self) -> Path:
        with pymupdf.open() as doc:
            for number in range(1, self._pages + 1):
                doc.new_page().insert_text(TEXT_ORIGIN, f"Page {number} of the work, with words enough to measure.")
            if self._outline:
                doc.set_toc(self._outline)
            doc.save(self._path)
        return self._path
