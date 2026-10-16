from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.filing import FilingCompletion
from _file.notes import CorpusNote
from _file.refile import RefileTarget, Refiler
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    ATTACHMENT_LINK,
    PDF_BYTES,
    PLACED_PDF_NAME,
    Citation,
    VaultTestCase,
    saved_with_key,
)
from _vaults import TextPdf


class PlacingConnector:
    def __init__(self, placed: Path) -> None:
        self._placed = placed

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self._placed.write_bytes(PDF_BYTES)
        return saved_with_key()


class AttachmentPolls:
    def __init__(self, placed: Path) -> None:
        self._placed = placed
        self.citekeys: list[str] = []

    def attachments(self, citekey: str) -> list[dict]:
        self.citekeys.append(citekey)
        return [{"path": str(self._placed), "open": ATTACHMENT_LINK}]


class TestARefileWhoseRecordZoteroGaveAnotherCitekey(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        library_pdf = TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.polls = AttachmentPolls(library_pdf)
        self.stub_zotero(save_item_with_attachment=PlacingConnector(library_pdf).save,
                         get_citation_key=lambda item_key: ASSIGNED_CITEKEY,
                         get_attachments=self.polls.attachments)
        self.report = Refiler(RefileTarget(PLACED_PDF_NAME), FilingCompletion()).execute()

    def test_the_placement_is_awaited_under_the_assigned_citekey(self) -> None:
        self.assertEqual({ASSIGNED_CITEKEY}, set(self.polls.citekeys))

    def test_the_report_names_the_assigned_citekey(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self.report["citekey"])

    def test_the_corpus_file_records_the_assigned_citekey(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, CorpusNote(PLACED_PDF_NAME).fields()["citekey"])



if __name__ == "__main__":
    unittest.main()
