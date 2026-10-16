from __future__ import annotations

from pathlib import Path

import vault
from _vault.frontmatter import FrontmatterFields

from _extract.failures import UsageFailure
from _extract.records import ExtractionRecords

__all__ = ["CorpusFile", "CorpusFileExists", "FrontmatterFields", "LibraryPdfs", "NoteMissing", "PdfLocator",
           "PdfNotFound"]



class PdfNotFound(UsageFailure, FileNotFoundError):
    pass


class CorpusFileExists(UsageFailure, FileExistsError):
    pass


class NoteMissing(UsageFailure, FileNotFoundError):
    pass


class PdfLocator:
    def resolve(self, raw: str) -> Path:
        located = vault.locate_pdf(raw, (vault.LIBRARY_DIR,))
        if located is None:
            raise PdfNotFound(f"PDF not found: {raw}")
        return located

    def with_note(self, raw: str) -> tuple[Path, CorpusFile]:
        pdf_path = self.resolve(raw)
        return pdf_path, CorpusFile(pdf_path).require_note()


class CorpusFile:
    def __init__(self, pdf_path: Path) -> None:
        self._basename = vault.basename_of(pdf_path)
        self._path = vault.corpus_path(self._basename)
        self._guarded = vault.GuardedNote(self._path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def basename(self) -> str:
        return self._basename


    def require_note(self) -> CorpusFile:
        if not self._path.is_file():
            raise NoteMissing(f"no corpus file for {self._basename}; run Stage 1 first ({self._path})")
        self._require_frontmatter()
        return self

    def _require_frontmatter(self) -> None:
        self._framed_parts()

    def _framed_parts(self) -> tuple[str, str]:
        frontmatter, body = vault.split_note(self._guarded.text())
        if not frontmatter:
            raise NoteMissing(
                f"corpus file for {self._basename} has no frontmatter block; run Stage 1 first ({self._path})")
        return frontmatter, body

    def frontmatter(self) -> dict:
        meta, _body = vault.read_frontmatter(self._path)
        return meta

    def has_body(self) -> bool:
        return self._path.is_file() and bool(self.body().strip())

    def reviewed(self) -> str | None:
        return ExtractionRecords().reviewed(self._basename)

    def require_absent(self) -> None:
        if vault.body_after_pdf_link(self._framed_parts()[1]).strip():
            raise CorpusFileExists(f"corpus file exists: {self._path}; pass --replace to rewrite it")

    def write(self, text: str, fields: dict) -> Path:
        self._guarded.replace(self._composed(self._framed_parts(), text, fields))
        return self._path

    def note_text_with(self, text: str, fields: dict) -> str:
        return self._composed(self._framed_parts(), text, fields)

    def _composed(self, parts: tuple[str, str], text: str, fields: dict) -> str:
        frontmatter, body = parts
        linked = vault.upsert_pdf_link(text, self._basename, vault.pdf_link_of(body))
        return vault.join_note(FrontmatterFields().upserted(frontmatter, fields), linked)

    def body(self) -> str:
        return vault.body_after_pdf_link(self._parts()[1])

    def _parts(self) -> tuple[str, str]:
        return vault.split_note(self._path.read_text(encoding="utf-8"))


class LibraryPdfs:
    def all(self) -> list[Path]:
        return vault.list_pdfs(vault.LIBRARY_DIR)

    def without_body(self) -> list[Path]:
        return [pdf for pdf in self.all() if not CorpusFile(pdf).has_body()]
