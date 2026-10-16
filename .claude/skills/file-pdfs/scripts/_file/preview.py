from __future__ import annotations

from pathlib import Path

import vault

from _file.bib import MetadataMerge
from _file.notes import DraftCard
from _file.citekeys import CitekeyAllocator
from _file.probe import PdfProbe

UNDATED_YEAR = vault.citekey_year({})


class FilingPreview:
    def __init__(self, pdf_path: Path, meta: dict) -> None:
        self._pdf_path = pdf_path
        self._meta = meta

    @classmethod
    def of(cls, pdf_path: Path) -> "FilingPreview":
        return cls.merged(pdf_path, DraftCard(pdf_path.name).load())

    @classmethod
    def merged(cls, pdf_path: Path, draft: DraftCard) -> "FilingPreview":
        meta = PdfProbe().of(pdf_path)
        MetadataMerge().into(meta, draft)
        return cls(pdf_path, meta)

    @property
    def meta(self) -> dict:
        return self._meta

    def library_filename(self) -> str:
        return vault.library_filename(self._surnames(), self._year(), self._title())

    def citekey(self) -> str:
        return CitekeyAllocator().for_meta(self._meta, exclude_stem=self._pdf_path.stem)

    def _title(self) -> str:
        return self._meta["bib"].get("shortTitle") or self._meta["title"]

    def _surnames(self) -> list[str]:
        return [author["lastName"] for author in self._meta["authors"]]

    def _year(self) -> str:
        return self._meta["year"] or UNDATED_YEAR
