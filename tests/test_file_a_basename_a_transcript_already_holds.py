from __future__ import annotations

from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault
import unittest
from zotero import ConnectorResult
from _file.filing import STATUS_DUPLICATE, Filer, FilingCompletion, FilingOutcome, PlacedAttachment, Placement
from _file.records import FiledRecordNote
from _file_fixtures import (
    ATTACHMENT_LINK,
    CITEKEY,
    CREDITED_DRAFT_CARD,
    INBOX_PDF_NAME,
    PDF_BYTES,
    PLACED_PDF_NAME,
    PREDICTED_PDF_NAME,
    Citation,
    VaultTestCase,
)
from _vaults import TextPdf

STATUS_HELD_AS_TRANSCRIPT = "held-as-transcript"


def refuse_to_save(item: dict, pdf: Path) -> ConnectorResult:
    raise AssertionError("a basename a transcript holds is never sent to Zotero")


class TranscriptTestCase(VaultTestCase):
    def hold_transcript(self, pdf_name: str) -> Path:
        transcript = vault.transcript_path(Path(pdf_name).stem)
        transcript.write_text("---\ntitle: A Talk\n---\n", encoding="utf-8")
        return transcript


class TestFilingUnderTheBasenameOfATranscript(TranscriptTestCase):
    def test_the_filing_is_refused_as_a_duplicate(self) -> None:
        inbox_pdf = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(CREDITED_DRAFT_CARD)
        self.hold_transcript(PREDICTED_PDF_NAME)
        self.stub_zotero(find_existing_citekey=lambda query: None, save_item_with_attachment=refuse_to_save)
        report = Filer(FilingCompletion()).file(inbox_pdf)
        self.assertEqual((STATUS_DUPLICATE, PREDICTED_PDF_NAME), (report["status"], report["held_as"]))


class TestAPlacementUnderTheBasenameOfATranscript(TranscriptTestCase):
    def test_the_completion_collides(self) -> None:
        placed = self.vault.library / PLACED_PDF_NAME
        placed.write_bytes(PDF_BYTES)
        self.hold_transcript(PLACED_PDF_NAME)
        outcome = FilingOutcome(self.vault.inbox / INBOX_PDF_NAME, Citation().meta(), CITEKEY,
                                ConnectorResult.saved(), Placement(PlacedAttachment(placed, ATTACHMENT_LINK)))
        self.assertTrue(FilingCompletion().collides(outcome))


class TestANoteForALibraryPdfWhoseBasenameATranscriptHolds(TranscriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        pdf = TextPdf(self.vault.library / PLACED_PDF_NAME).write()
        self.transcript = self.hold_transcript(PLACED_PDF_NAME)
        self.report = FiledRecordNote(pdf).preview()

    def test_the_note_is_refused_as_held_by_a_transcript(self) -> None:
        self.assertEqual(STATUS_HELD_AS_TRANSCRIPT, self.report["status"])

    def test_the_report_names_the_transcript(self) -> None:
        self.assertEqual(str(self.transcript), self.report["detail"])


class TestTheHeldNoteHelper(TranscriptTestCase):
    def test_a_basename_only_a_transcript_carries_is_held(self) -> None:
        self.hold_transcript(PLACED_PDF_NAME)
        self.assertTrue(vault.held_note_exists(Path(PLACED_PDF_NAME).stem))

    def test_a_basename_no_note_carries_is_not_held(self) -> None:
        self.assertFalse(vault.held_note_exists(Path(PLACED_PDF_NAME).stem))


if __name__ == "__main__":
    unittest.main()
