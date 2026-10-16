from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from zotero import ConnectorResult
from _file.notes import CorpusNote
from _file.filing import FilingCompletion
from _file.refile import REFILING_DIR_NAME, STATUS_REFILE_FAILED, STATUS_REFILED, RefileTarget, Refiler
from _file_fixtures import (
    ATTACHMENT_LINK,
    CITEKEY,
    PLACED_PDF_NAME,
    Citation,
    VaultTestCase,
)
from _vaults import TextPdf
from _file_filing_fixtures import MovingConnector


class TestRefileHoldsThePdfInsideTheLibrary(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.stub_zotero(save_item_with_attachment=lambda item, pdf: ConnectorResult.refused())
        self.report = Refiler(RefileTarget(PLACED_PDF_NAME), FilingCompletion()).execute()

    def test_a_refused_refile_reports_the_failure(self) -> None:
        self.assertEqual(STATUS_REFILE_FAILED, self.report["status"])

    def test_a_refused_refile_restores_the_library_pdf(self) -> None:
        self.assertTrue((self.vault.library / PLACED_PDF_NAME).exists())

    def test_the_holding_copy_sits_in_the_synced_library_tree(self) -> None:
        self.assertTrue((self.vault.library / REFILING_DIR_NAME / PLACED_PDF_NAME).exists())

    def test_nothing_is_held_in_the_unsynced_scratch_directory(self) -> None:
        self.assertEqual([], list(vault.SCRATCH_DIR.glob("*.pdf")))

    def test_the_holding_copy_is_not_listed_as_a_library_pdf(self) -> None:
        self.assertEqual([PLACED_PDF_NAME], [path.name for path in vault.list_pdfs(self.vault.library)])


class TestAVerifiedRefileCompletes(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library_pdf = TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "## One\n\nkept\n")
        self.stub_zotero(save_item_with_attachment=MovingConnector(self.library_pdf).save,
                         get_citation_key=lambda item_key: CITEKEY,
                         get_attachments=lambda citekey: [{"path": str(self.library_pdf), "open": ATTACHMENT_LINK}])
        self.report = Refiler(RefileTarget(PLACED_PDF_NAME), FilingCompletion()).execute()

    def test_the_status_is_refiled_under_the_placed_name(self) -> None:
        self.assertEqual((STATUS_REFILED, PLACED_PDF_NAME), (self.report["status"], self.report["file"]))

    def test_the_holding_copy_is_discarded(self) -> None:
        self.assertFalse((self.vault.library / REFILING_DIR_NAME / PLACED_PDF_NAME).exists())

    def test_the_library_pdf_survives(self) -> None:
        self.assertTrue(self.library_pdf.exists())

    def test_the_body_survives(self) -> None:
        self.assertIn("kept", CorpusNote(PLACED_PDF_NAME).body())


if __name__ == "__main__":
    unittest.main()
