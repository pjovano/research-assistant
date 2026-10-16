from __future__ import annotations

from pathlib import Path

import vault


class PdfLocator:
    def in_inbox(self, name: str) -> Path:
        return self._located(name, (vault.INBOX_DIR,), "the inbox")

    def in_library(self, name: str) -> Path:
        return self._located(name, (vault.LIBRARY_DIR,), "the library")

    def inbox_or_filed(self, name: str) -> Path:
        return self._located(name, (vault.INBOX_DIR, vault.LIBRARY_DIR), "the inbox or the library")

    def _located(self, name: str, search_dirs: tuple[Path, ...], where: str) -> Path:
        located = vault.locate_pdf(name, search_dirs)
        if located is None:
            raise SystemExit(f"Not found in {where}: {name}")
        return located


class NotePaths:
    def draft(self, pdf_name: str) -> Path:
        return vault.INBOX_DIR / f"{Path(pdf_name).stem}{vault.NOTE_SUFFIX}"

    def note(self, pdf_name: str) -> Path:
        return vault.corpus_path(Path(pdf_name).stem)

    def pdf_name_of(self, note_path: Path) -> str:
        return f"{note_path.stem}{vault.PDF_SUFFIX}"

    def drafts(self) -> list[Path]:
        return vault.list_markdown(vault.INBOX_DIR)

    def notes(self) -> list[Path]:
        return vault.list_corpus_files()

    def ensure_dirs(self) -> None:
        vault.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
