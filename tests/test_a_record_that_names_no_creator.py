from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import transcribe
import vault
from zotero import ConnectorResult
from _file.cli import Commands
from _file.filing import STATUS_NO_CREATOR, Filer, FilingCompletion
from _file.retry import RetryRunner
from _file_fixtures import INBOX_PDF_NAME, VaultTestCase
from _transcribe_fixtures import CARD, Review, TalkTestCase
from _vaults import TextPdf

UNFILED_CARD_WITHOUT_CREATORS = "---\nzotero:\n  title: A Work\n  date: '2020'\nfiled: false\n---\n"
EXIT_FAILURE = 1


class ConnectorThatMustNotBeCalled:
    def __init__(self) -> None:
        self.calls = 0

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self.calls += 1
        return ConnectorResult.saved()


class TestTheLibraryFilenameOfARecordWithNoCreator(unittest.TestCase):
    def test_the_creator_of_no_surnames_is_refused(self) -> None:
        with self.assertRaises(vault.CreatorMissing):
            vault.format_creator([])

    def test_the_library_filename_of_no_surnames_is_refused(self) -> None:
        with self.assertRaises(vault.CreatorMissing):
            vault.library_filename([], "2020", "A Work")

    def test_the_refusal_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(vault.CreatorMissing, ValueError))

    def test_the_former_name_builds_the_same_filename(self) -> None:
        self.assertIs(vault.library_filename, vault.library_filename_verbatim)


class TestFilingAPdfWhoseRecordNamesNoCreator(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.inbox_pdf = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.connector = ConnectorThatMustNotBeCalled()
        self.stub_zotero(find_existing_citekey=lambda query: None,
                         save_item_with_attachment=self.connector.save)
        self.row = Filer(FilingCompletion()).file(self.inbox_pdf)

    def test_the_row_reports_no_creator(self) -> None:
        self.assertEqual(STATUS_NO_CREATOR, self.row["status"])

    def test_the_row_carries_the_refusal(self) -> None:
        self.assertTrue(self.row["message"])

    def test_zotero_is_never_asked_to_save_the_item(self) -> None:
        self.assertEqual(0, self.connector.calls)


class TestRetryingAPdfWhoseRecordNamesNoCreator(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(UNFILED_CARD_WITHOUT_CREATORS)
        self.connector = ConnectorThatMustNotBeCalled()
        self.stub_zotero(is_online=lambda timeout=None: True,
                         find_existing_citekey=lambda query: None,
                         save_item_with_attachment=self.connector.save)
        self.rows = RetryRunner(FilingCompletion()).run()

    def test_the_row_reports_no_creator(self) -> None:
        self.assertEqual([STATUS_NO_CREATOR], [row["status"] for row in self.rows])

    def test_zotero_is_never_asked_to_save_the_item(self) -> None:
        self.assertEqual(0, self.connector.calls)


class TestNamingAPdfWhoseRecordNamesNoCreator(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        inbox_pdf = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.printed = io.StringIO()
        with contextlib.redirect_stdout(self.printed), self.assertRaises(SystemExit) as exit_status:
            Commands().name(argparse.Namespace(pdf=str(inbox_pdf)))
        self.exit_code = exit_status.exception.code

    def test_the_command_exits_with_failure(self) -> None:
        self.assertEqual(EXIT_FAILURE, self.exit_code)

    def test_the_command_prints_the_refusal_as_json(self) -> None:
        self.assertTrue(json.loads(self.printed.getvalue())["error"])


class TestFilingATalkWhoseCardNamesNoPresenter(TalkTestCase):
    def test_the_basename_is_refused_naming_the_missing_presenters(self) -> None:
        record = transcribe.TalkRecord(self.reviewed(review=Review(card={**CARD, "presenters": []})))
        with self.assertRaisesRegex(transcribe.FilingRefused, "presenter"):
            record.basename


if __name__ == "__main__":
    unittest.main()
