from __future__ import annotations

import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import zotero
from zotero import ConnectorResult
from _file.notes import NoteFrontmatter
from _vaults import TEXT_ORIGIN, TempVault

FILING_DIRS = ("INBOX_DIR", "LIBRARY_DIR", "CORPUS_DIR")
CITEKEY = "doe2020"
ASSIGNED_CITEKEY = "doe2020a"
ZOTERO_ITEM_KEY = "ABCD1234"
INBOX_PDF_NAME = "scan.pdf"
DRAFT_CARD_NAME = f"{Path(INBOX_PDF_NAME).stem}.md"
PLACED_PDF_NAME = "Doe - 2020 - A Work.pdf"
PLACED_NOTE_NAME = "Doe - 2020 - A Work.md"
PREDICTED_PDF_NAME = "Doe - n.d. - scan.pdf"
OTHER_WORK_PDF_NAME = "Roe - 2019 - Another Work.pdf"
VERIFIED_PDF_NAME = "Doe - 2020 - A Work.pdf"
ATTACHMENT_LINK = f"zotero://open-pdf/library/items/{ZOTERO_ITEM_KEY}"
PDF_BYTES = b"%PDF-1.7\n"
RECORDED_ISBN = "9780000000002"
AMENDED_NAME_REASON = "The printed title names only its figure; the subject is the volume's."
UNCITABLE_REASON = "A scan of a later reprint; the folios are not the published ones."
RECORDED_CREATORS = "  creators:\n  - creatorType: author\n    lastName: Doe\n"
CREDITED_DRAFT_CARD = f"---\nzotero:\n{RECORDED_CREATORS}---\n"
DATED_DRAFT_CARD = f"---\nzotero:\n  title: A Work\n  date: '2020'\n{RECORDED_CREATORS}---\n"


def saved_with_key(item_key: str = ZOTERO_ITEM_KEY) -> ConnectorResult:
    return ConnectorResult(True, True, True, item_key=item_key)


def saved_without_attachment() -> ConnectorResult:
    return ConnectorResult(True, True, False)


class Citation:
    def __init__(self, extra: object = None) -> None:
        self._extra = extra

    def meta(self) -> dict:
        return {"title": "A Work", "authors": [{"lastName": "Doe"}], "year": "2020",
                "type": "book", "bib": {"extra": self._extra}}

    def fields(self) -> dict:
        return NoteFrontmatter(self.meta(), CITEKEY).fields()


class StubbedZotero:
    def __init__(self, **attributes) -> None:
        self._attributes = attributes
        self._saved = {name: getattr(zotero, name) for name in attributes}

    def activate(self) -> "StubbedZotero":
        for name, value in self._attributes.items():
            setattr(zotero, name, value)
        return self

    def discard(self) -> None:
        for name, value in self._saved.items():
            setattr(zotero, name, value)


class IdentifiedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._pages: list[str] = ["A page of the work."]
        self._xmp: str | None = None

    def with_pages(self, *texts: str) -> "IdentifiedPdf":
        self._pages = list(texts)
        return self

    def with_xmp(self, xmp: str) -> "IdentifiedPdf":
        self._xmp = xmp
        return self

    def write(self) -> Path:
        with pymupdf.open() as doc:
            for text in self._pages:
                doc.new_page().insert_text(TEXT_ORIGIN, text)
            if self._xmp:
                doc.set_xml_metadata(self._xmp)
            doc.save(self._path)
        return self._path


class VaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*FILING_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.stub_zotero(held_citekeys_beginning=lambda prefix: set())

    def stub_zotero(self, **attributes) -> None:
        self.addCleanup(StubbedZotero(**attributes).activate().discard)

    def pdf(self, name: str = INBOX_PDF_NAME) -> IdentifiedPdf:
        return IdentifiedPdf(self.vault.inbox / name)

    def draft_card(self, text: str) -> Path:
        card = self.vault.inbox / DRAFT_CARD_NAME
        card.write_text(text, encoding="utf-8")
        return card
