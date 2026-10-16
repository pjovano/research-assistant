from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.cli import Commands
from _file.filing import FilingCompletion
from _file.retry import RetryRunner
from _file_fixtures import CITEKEY, DATED_DRAFT_CARD, INBOX_PDF_NAME, VaultTestCase
from _vaults import TextPdf

OTHER_CARD = "pending.md"
OTHER_PDF_NAME = f"{Path(OTHER_CARD).stem}.pdf"
OTHER_CARD_TEXT = DATED_DRAFT_CARD


class RecordingOfflineConnector:
    def __init__(self) -> None:
        self.posted: list[str] = []

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self.posted.append(pdf.name)
        return ConnectorResult.offline()


class InboxWithAnotherUnfiledDraftCard(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        TextPdf(self.vault.inbox / OTHER_PDF_NAME, pages=1).write()
        self.draft_card(f"---\ncitekey: {CITEKEY}\nfiled: false\n---\n")
        (self.vault.inbox / OTHER_CARD).write_text(OTHER_CARD_TEXT, encoding="utf-8")
        self.connector = RecordingOfflineConnector()
        self.stub_zotero(is_online=lambda timeout=None: True,
                         holds_titled_record=lambda citekey, title: False,
                         find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         save_item_with_attachment=self.connector.save)

    def assert_the_other_pdf_was_never_posted(self) -> None:
        self.assertNotIn(OTHER_PDF_NAME, self.connector.posted)


class TestFileOnlyFilesTheNamedPdfAlone(InboxWithAnotherUnfiledDraftCard):
    def setUp(self) -> None:
        super().setUp()
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            Commands().file(argparse.Namespace(pdf=INBOX_PDF_NAME, only=True))
        self.report = json.loads(printed.getvalue())

    def test_no_other_draft_card_is_resumed(self) -> None:
        self.assertEqual([], self.report["retried_pending"])

    def test_the_named_pdf_is_filed(self) -> None:
        self.assertEqual([INBOX_PDF_NAME], [row["file"] for row in self.report["filed"]])

    def test_the_other_pdf_is_never_posted_to_zotero(self) -> None:
        self.assert_the_other_pdf_was_never_posted()


class TestRetryForOnePdfRetriesItsDraftCardAlone(InboxWithAnotherUnfiledDraftCard):
    def setUp(self) -> None:
        super().setUp()
        self.rows = RetryRunner(FilingCompletion()).run_for(INBOX_PDF_NAME)

    def test_only_the_named_pdfs_draft_card_is_retried(self) -> None:
        self.assertEqual([INBOX_PDF_NAME], [row["file"] for row in self.rows])

    def test_the_other_pdf_is_never_posted_to_zotero(self) -> None:
        self.assert_the_other_pdf_was_never_posted()
