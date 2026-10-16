from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.notes import CorpusNote, DraftCard
from _file.filing import (
    STATUS_DUPLICATE,
    STATUS_FILED,
    STATUS_FILED_UNVERIFIED,
    AttachmentWatcher,
    Filer,
    FilingCompletion,
    FilingOutcome,
    Placement,
    Settlement,
)
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    ATTACHMENT_LINK,
    CITEKEY,
    CREDITED_DRAFT_CARD,
    DATED_DRAFT_CARD,
    INBOX_PDF_NAME,
    OTHER_WORK_PDF_NAME,
    PDF_BYTES,
    PLACED_PDF_NAME,
    PREDICTED_PDF_NAME,
    VERIFIED_PDF_NAME,
    Citation,
    VaultTestCase,
)
from _vaults import TextPdf
from _file_filing_fixtures import MovingConnector


class TestLibraryMembership(VaultTestCase):
    def _in_library(self, name: str) -> bool:
        path = self.vault.library / name
        path.write_bytes(PDF_BYTES)
        return AttachmentWatcher(PLACED_PDF_NAME).in_library(path)

    def test_a_library_pdf_on_the_convention_is_in_the_library(self) -> None:
        self.assertTrue(self._in_library(PLACED_PDF_NAME))

    def test_a_library_pdf_off_the_convention_is_not_in_the_library(self) -> None:
        self.assertFalse(self._in_library("Doe - A Work.pdf"))

    def test_a_pdf_outside_the_library_is_not_in_the_library(self) -> None:
        outside = self.vault.inbox / PLACED_PDF_NAME
        outside.write_bytes(PDF_BYTES)
        self.assertFalse(AttachmentWatcher(PLACED_PDF_NAME).in_library(outside))


class TestPlacementIsVerifiedAgainstThePredictedName(VaultTestCase):
    def _placement(self, attachment_name: str) -> Placement:
        path = self.vault.library / attachment_name
        path.write_bytes(PDF_BYTES)
        self.stub_zotero(get_attachments=lambda citekey: [{"path": str(path), "open": ATTACHMENT_LINK}])
        return AttachmentWatcher(PLACED_PDF_NAME, timeout=0).await_placement(CITEKEY)

    def test_an_attachment_under_the_predicted_name_verifies_the_placement(self) -> None:
        self.assertEqual(PLACED_PDF_NAME, self._placement(PLACED_PDF_NAME).verified.pdf_name)

    def test_another_works_pdf_under_the_same_citekey_does_not_verify(self) -> None:
        self.assertIsNone(self._placement(OTHER_WORK_PDF_NAME).verified)

    def test_another_works_pdf_under_the_same_citekey_is_named(self) -> None:
        self.assertEqual(OTHER_WORK_PDF_NAME, self._placement(OTHER_WORK_PDF_NAME).other_name)


class TestPlacedElsewhereIsReported(VaultTestCase):
    def _summary(self) -> dict:
        outcome = FilingOutcome(self.vault.inbox / INBOX_PDF_NAME, Citation().meta(), CITEKEY,
                                ConnectorResult.saved(), Placement(None, OTHER_WORK_PDF_NAME))
        settlement = Settlement(FilingCompletion(), DraftCard(INBOX_PDF_NAME).load(), outcome)
        return Filer(FilingCompletion())._summary(outcome, settlement.status)

    def test_a_filing_placed_under_another_name_is_unverified(self) -> None:
        self.assertEqual(STATUS_FILED_UNVERIFIED, self._summary()["status"])

    def test_the_payload_names_the_pdf_placed_under_another_name(self) -> None:
        self.assertEqual(OTHER_WORK_PDF_NAME, self._summary()["placed_elsewhere"])


class TestDuplicateGuard(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.inbox_pdf = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(CREDITED_DRAFT_CARD)

    def test_a_work_already_in_the_library_under_the_predicted_name_is_refused(self) -> None:
        (self.vault.library / PREDICTED_PDF_NAME).write_bytes(PDF_BYTES)
        report = Filer(FilingCompletion()).file(self.inbox_pdf)
        self.assertEqual((STATUS_DUPLICATE, PREDICTED_PDF_NAME), (report["status"], report["held_as"]))

    def test_a_corpus_file_already_under_the_predicted_name_is_refused(self) -> None:
        note_name = Path(PREDICTED_PDF_NAME).with_suffix(".md").name
        (self.vault.corpus / note_name).write_text("---\ntitle: Held\n---\n", encoding="utf-8")
        self.assertEqual(STATUS_DUPLICATE, Filer(FilingCompletion()).file(self.inbox_pdf)["status"])


class TestAVerifiedFilingIsReportedFiled(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        inbox_pdf = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(DATED_DRAFT_CARD)
        placed = self.vault.library / VERIFIED_PDF_NAME
        self.stub_zotero(find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         save_item_with_attachment=MovingConnector(placed).save,
                         get_citation_key=lambda item_key: ASSIGNED_CITEKEY,
                         get_attachments=lambda citekey: [{"path": str(placed), "open": ATTACHMENT_LINK}])
        self.report = Filer(FilingCompletion()).file(inbox_pdf)

    def test_the_status_is_filed(self) -> None:
        self.assertEqual(STATUS_FILED, self.report["status"])

    def test_the_report_names_the_placed_pdf(self) -> None:
        self.assertEqual(VERIFIED_PDF_NAME, self.report["file"])

    def test_the_corpus_file_is_written_under_the_placed_name(self) -> None:
        self.assertTrue(CorpusNote(VERIFIED_PDF_NAME).exists())


if __name__ == "__main__":
    unittest.main()
