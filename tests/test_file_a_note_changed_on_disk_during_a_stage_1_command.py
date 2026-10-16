from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.cli import Commands, main
from _file.filing import STATUS_NOTE_CHANGED_ON_DISK
from _file.notes import CorpusNote, DraftCard
from _file.records import ZoteroDatabase
from _file_fixtures import (
    ATTACHMENT_LINK,
    CITEKEY,
    DATED_DRAFT_CARD,
    INBOX_PDF_NAME,
    PLACED_PDF_NAME,
    ZOTERO_ITEM_KEY,
    Citation,
    VaultTestCase,
    saved_with_key,
)
from _vaults import TextPdf

FOREIGN_TEXT = "---\ntitle: Written by hand meanwhile\n---\n"
PENDING_CARD = DATED_DRAFT_CARD.replace("---\n", f"---\ncitekey: {CITEKEY}\nfiled: false\n", 1)
LATER_CARD_NAME = "tail.md"
CSL_BOOK = {"type": "book", "title": "A Work", "author": [{"family": "Doe"}], "issued": {"date-parts": [[2020]]}}


class ForeignEdit:
    def __init__(self, note: Path) -> None:
        self._note = note
        self.calls = 0

    def write(self) -> None:
        self.calls += 1
        self._note.write_text(FOREIGN_TEXT, encoding="utf-8")


class EditingConnector:
    def __init__(self, edit: ForeignEdit, result: ConnectorResult) -> None:
        self._edit = edit
        self._result = result

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self._edit.write()
        return self._result


class CommandRun:
    def __init__(self, command: object) -> None:
        self._command = command
        self.exit_code: object = 0

    def report(self, args: argparse.Namespace) -> object:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self._run(args)
        return json.loads(printed.getvalue())

    def _run(self, args: argparse.Namespace) -> None:
        try:
            self._command(args)
        except SystemExit as stopped:
            self.exit_code = stopped.code


class FilingTestCase(VaultTestCase):
    def stub_filing(self, connector: EditingConnector) -> None:
        self.stub_zotero(is_online=lambda timeout=None: True,
                         holds_titled_record=lambda citekey, title: False,
                         find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         get_citation_key=lambda item_key: CITEKEY,
                         get_attachments=lambda citekey: [],
                         save_item_with_attachment=connector.save)


class TestRetryOverADraftCardChangedOnDisk(FilingTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        TextPdf(self.vault.inbox / f"{Path(LATER_CARD_NAME).stem}.pdf", pages=1).write()
        self.card = self.draft_card(PENDING_CARD)
        (self.vault.inbox / LATER_CARD_NAME).write_text(PENDING_CARD, encoding="utf-8")
        self.edit = ForeignEdit(self.card)
        self.stub_filing(EditingConnector(self.edit, saved_with_key()))
        self.run = CommandRun(Commands().retry)
        self.rows = self.run.report(argparse.Namespace(only=None))

    def test_the_row_reports_the_note_changed_on_disk(self) -> None:
        self.assertEqual(STATUS_NOTE_CHANGED_ON_DISK, self.rows[0]["status"])

    def test_the_row_names_the_changed_draft_card(self) -> None:
        self.assertEqual(str(self.card), self.rows[0]["path"])

    def test_no_later_draft_card_is_filed(self) -> None:
        self.assertEqual((1, 1), (self.edit.calls, len(self.rows)))

    def test_the_foreign_edit_survives(self) -> None:
        self.assertEqual(FOREIGN_TEXT, self.card.read_text(encoding="utf-8"))

    def test_the_command_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.run.exit_code)


class TestFileOfAPdfWhoseDraftCardChangesOnDisk(FilingTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.card = self.draft_card(DATED_DRAFT_CARD)
        self.stub_filing(EditingConnector(ForeignEdit(self.card), ConnectorResult.offline()))
        self.run = CommandRun(Commands().file)
        self.report = self.run.report(argparse.Namespace(pdf=INBOX_PDF_NAME, only=False))

    def test_the_filed_row_reports_the_note_changed_on_disk(self) -> None:
        self.assertEqual((STATUS_NOTE_CHANGED_ON_DISK, str(self.card)),
                         (self.report["filed"][0]["status"], self.report["filed"][0]["path"]))

    def test_the_command_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.run.exit_code)


class TestFileWhoseResumePassMeetsADraftCardChangedOnDisk(FilingTestCase):
    NAMED_PDF_NAME = "named.pdf"

    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        TextPdf(self.vault.inbox / self.NAMED_PDF_NAME, pages=1).write()
        self.card = self.draft_card(PENDING_CARD)
        self.edit = ForeignEdit(self.card)
        self.stub_filing(EditingConnector(self.edit, saved_with_key()))
        self.run = CommandRun(Commands().file)
        self.report = self.run.report(argparse.Namespace(pdf=self.NAMED_PDF_NAME, only=False))

    def test_the_resume_row_reports_the_note_changed_on_disk(self) -> None:
        self.assertEqual(STATUS_NOTE_CHANGED_ON_DISK, self.report["retried_pending"][0]["status"])

    def test_the_named_pdf_is_not_filed(self) -> None:
        self.assertEqual(([], 1), (self.report["filed"], self.edit.calls))

    def test_the_command_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.run.exit_code)


class CorpusFileWrittenDuringTheLookup:
    def __init__(self, note: Path) -> None:
        self._edit = ForeignEdit(note)

    def record(self, citekey: str) -> dict:
        self._edit.write()
        return CSL_BOOK


class TestNoteApplyOverACorpusFileWrittenMeanwhile(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.library / PLACED_PDF_NAME).write()
        self.note = CorpusNote(PLACED_PDF_NAME).path
        self.stub_zotero(is_online=lambda timeout=None: True, get_citation_key=lambda item_key: CITEKEY,
                         build_pdf_link=lambda citekey: ATTACHMENT_LINK,
                         get_csl_record=CorpusFileWrittenDuringTheLookup(self.note).record)
        self.run = CommandRun(Commands().note)
        with mock.patch.object(ZoteroDatabase, "parent_item_key", return_value=ZOTERO_ITEM_KEY):
            self.row = self.run.report(argparse.Namespace(pdf=PLACED_PDF_NAME, apply=True))

    def test_the_row_reports_the_note_changed_on_disk(self) -> None:
        self.assertEqual((STATUS_NOTE_CHANGED_ON_DISK, str(self.note)), (self.row["status"], self.row["path"]))

    def test_the_command_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.run.exit_code)


class TestRefileWhoseDraftCardAppearsOnDisk(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library_pdf = TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.card = DraftCard(PLACED_PDF_NAME).path
        self.stub_zotero(save_item_with_attachment=EditingConnector(ForeignEdit(self.card), saved_with_key()).save,
                         get_citation_key=lambda item_key: CITEKEY)
        self.run = CommandRun(Commands().refile)
        self.row = self.run.report(argparse.Namespace(pdf=PLACED_PDF_NAME, allow_incomplete=True,
                                                      stale_item_deleted=True))

    def test_the_row_reports_the_note_changed_on_disk(self) -> None:
        self.assertEqual((STATUS_NOTE_CHANGED_ON_DISK, str(self.card)), (self.row["status"], self.row["path"]))

    def test_the_pdf_is_back_in_the_library(self) -> None:
        self.assertTrue(self.library_pdf.exists())

    def test_the_command_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.run.exit_code)


class CitekeysReadWhileTheCardIsEdited:
    def __init__(self, card: Path) -> None:
        self._edit = ForeignEdit(card)

    def held(self, prefix: str) -> set:
        self._edit.write()
        return set()


class TestBibSetOnADraftCardChangedOnDisk(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.card = self.draft_card(DATED_DRAFT_CARD)
        self.stub_zotero(held_citekeys_beginning=CitekeysReadWhileTheCardIsEdited(self.card).held)
        self.run = CommandRun(lambda _args: main())
        argv = ["file.py", "bib", INBOX_PDF_NAME, "--set", "place=Berlin"]
        with mock.patch.object(sys, "argv", argv):
            self.report = self.run.report(argparse.Namespace())

    def test_the_error_names_the_changed_draft_card(self) -> None:
        self.assertEqual(str(self.card), self.report["path"])

    def test_the_error_says_nothing_was_written(self) -> None:
        self.assertIn("nothing was written", self.report["error"])

    def test_the_command_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.run.exit_code)

    def test_the_foreign_edit_survives(self) -> None:
        self.assertEqual(FOREIGN_TEXT, self.card.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
