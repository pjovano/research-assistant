from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.filing import AttachmentWatcher, FilingCompletion, Placement
from _file.notes import CorpusNote
from _file.refile import REFILING_DIR_NAME, RefileTarget, Refiler
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


class TestAnUnverifiedRefileWhoseNameTheLibraryAlreadyHoldsAgain(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        library_pdf = TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.stub_zotero(save_item_with_attachment=PlacingConnector(library_pdf).save,
                         get_citation_key=lambda item_key: ASSIGNED_CITEKEY)
        with mock.patch.object(AttachmentWatcher, "await_placement", return_value=Placement()):
            self.report = Refiler(RefileTarget(PLACED_PDF_NAME), FilingCompletion()).execute()

    def test_the_report_does_not_claim_the_pdf_was_restored(self) -> None:
        self.assertNotIn("restored", self.report["note"])

    def test_the_report_names_the_holding_copy(self) -> None:
        self.assertEqual(str(self.vault.library / REFILING_DIR_NAME / PLACED_PDF_NAME), self.report["holding"])


if __name__ == "__main__":
    unittest.main()
