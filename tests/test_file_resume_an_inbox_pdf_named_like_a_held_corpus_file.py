from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.filing import (
    STATUS_ALREADY_FILED,
    FilingCompletion,
    FilingOutcome,
    PlacedAttachment,
    Placement,
)
from _file.notes import CorpusNote
from _file.preview import FilingPreview
from _file.retry import RetryRunner
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    ATTACHMENT_LINK,
    OTHER_WORK_PDF_NAME,
    PDF_BYTES,
    Citation,
    VaultTestCase,
    saved_with_key,
)
from _vaults import TextPdf

HELD_TEXT = "the body of the work already filed"
HELD_BODY = f"## Held\n\n{HELD_TEXT}\n"
PENDING_CARD = "---\nfiled: false\nzotero:\n  title: A Work\n  date: '2020'\n---\n"


class PlacingConnector:
    def __init__(self, placed: Path) -> None:
        self._placed = placed
        self.calls = 0

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self.calls += 1
        self._placed.write_bytes(PDF_BYTES)
        return saved_with_key()


class HeldBasenameTestCase(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.inbox_pdf = TextPdf(self.vault.inbox / OTHER_WORK_PDF_NAME, pages=1).write()
        (self.vault.inbox / Path(OTHER_WORK_PDF_NAME).with_suffix(".md").name).write_text(PENDING_CARD,
                                                                                          encoding="utf-8")
        CorpusNote(OTHER_WORK_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, HELD_BODY)
        self.placed = self.vault.library / FilingPreview.of(self.inbox_pdf).library_filename()


class TestAResumedFilingWhoseInboxNameIsAHeldBasename(HeldBasenameTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.connector = PlacingConnector(self.placed)
        self.stub_zotero(is_online=lambda timeout=None: True,
                         holds_titled_record=lambda citekey, title: False,
                         find_existing_citekey=lambda query: None,
                         save_item_with_attachment=self.connector.save,
                         get_citation_key=lambda item_key: ASSIGNED_CITEKEY,
                         get_attachments=lambda citekey: [{"path": str(self.placed), "open": ATTACHMENT_LINK}])
        self.rows = RetryRunner(FilingCompletion()).run()

    def test_the_row_reports_the_basename_already_filed(self) -> None:
        self.assertEqual([STATUS_ALREADY_FILED], [row["status"] for row in self.rows])

    def test_no_record_is_created(self) -> None:
        self.assertEqual(0, self.connector.calls)

    def test_the_held_corpus_file_keeps_its_body(self) -> None:
        self.assertIn(HELD_TEXT, CorpusNote(OTHER_WORK_PDF_NAME).body())


class TestACompletedFilingOfAnInboxPdfNamedLikeAHeldCorpusFile(HeldBasenameTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.placed.write_bytes(PDF_BYTES)
        outcome = FilingOutcome(self.inbox_pdf, Citation().meta(), ASSIGNED_CITEKEY, ConnectorResult.saved(),
                                Placement(PlacedAttachment(self.placed, ATTACHMENT_LINK)))
        FilingCompletion().complete(outcome)

    def test_the_held_corpus_file_keeps_its_body(self) -> None:
        self.assertIn(HELD_TEXT, CorpusNote(OTHER_WORK_PDF_NAME).body())

    def test_the_new_corpus_file_carries_none_of_its_body(self) -> None:
        self.assertNotIn(HELD_TEXT, CorpusNote(self.placed.name).body())


if __name__ == "__main__":
    unittest.main()
