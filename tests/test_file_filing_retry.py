from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import zotero
from zotero import ConnectorResult
from _file.cli import Commands
from _file.filing import (
    STATUS_DUPLICATE_IN_ZOTERO,
    FilingCompletion,
)
from _file.retry import STATUS_ZOTERO_STILL_OFFLINE, RetryRunner
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    ATTACHMENT_LINK,
    CITEKEY,
    INBOX_PDF_NAME,
    PDF_BYTES,
    RECORDED_CREATORS,
    VERIFIED_PDF_NAME,
    VaultTestCase,
)
from _vaults import TextPdf
from _file_filing_fixtures import (
    FakeResponse,
    FakeHttp,
)


class TestRetryWhileZoteroIsOffline(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.draft_card(f"---\ncitekey: {CITEKEY}\nfiled: false\n---\n")
        self.stub_zotero(is_online=lambda timeout=None: False)
        self.rows = RetryRunner(FilingCompletion()).run()

    def test_every_pending_draft_card_is_reported(self) -> None:
        self.assertEqual([INBOX_PDF_NAME], [row["file"] for row in self.rows])

    def test_the_row_says_zotero_is_still_offline(self) -> None:
        self.assertEqual(STATUS_ZOTERO_STILL_OFFLINE, self.rows[0]["status"])

    def test_the_row_keeps_the_citekey_the_card_carries(self) -> None:
        self.assertEqual(CITEKEY, self.rows[0]["citekey"])


class TestFileResumesOnlyTheUnfiledDraftCards(VaultTestCase):
    FILED_CARD = "filed.md"
    UNFILED_CARD = "pending.md"
    UNFILED_PDF_NAME = f"{Path(UNFILED_CARD).stem}.pdf"

    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        (self.vault.inbox / self.FILED_CARD).write_text("---\ncitekey: roe2019\nfiled: true\n---\n", encoding="utf-8")
        (self.vault.inbox / self.UNFILED_CARD).write_text("---\ncitekey: poe2018\nfiled: false\n---\n",
                                                          encoding="utf-8")
        self.stub_zotero(is_online=lambda timeout=None: False,
                         find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         save_item_with_attachment=lambda item, pdf: ConnectorResult.offline())
        self.report = self._file()

    def _file(self) -> dict:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            Commands().file(argparse.Namespace(pdf=INBOX_PDF_NAME, only=False))
        return json.loads(printed.getvalue())

    def test_the_resume_pass_retries_only_the_unfiled_draft_card(self) -> None:
        self.assertEqual([self.UNFILED_PDF_NAME], [row["file"] for row in self.report["retried_pending"]])

    def test_the_named_pdf_is_still_filed(self) -> None:
        self.assertEqual([INBOX_PDF_NAME], [row["file"] for row in self.report["filed"]])


class TestFileNeverResumesTheNamedPdfsOwnDraftCard(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(f"---\ncitekey: {CITEKEY}\nfiled: false\n---\n")
        self.stub_zotero(is_online=lambda timeout=None: False,
                         find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         save_item_with_attachment=lambda item, pdf: ConnectorResult.offline())
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            Commands().file(argparse.Namespace(pdf=INBOX_PDF_NAME, only=False))
        self.report = json.loads(printed.getvalue())

    def test_the_resume_pass_skips_the_card_of_the_pdf_being_filed(self) -> None:
        self.assertEqual([], self.report["retried_pending"])

    def test_the_named_pdf_is_filed_through_its_own_path(self) -> None:
        self.assertEqual([INBOX_PDF_NAME], [row["file"] for row in self.report["filed"]])


class RefusedConnector:
    def __init__(self) -> None:
        self.calls = 0

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self.calls += 1
        return ConnectorResult.saved()


class TestRetryRefusesAWorkZoteroAlreadyHolds(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(f"---\ncitekey: {CITEKEY}\nfiled: false\n---\n")
        self.connector = RefusedConnector()
        self.stub_zotero(is_online=lambda timeout=None: True,
                         holds_titled_record=lambda citekey, title: False,
                         find_existing_citekey=lambda title, doi=None, isbn=None: ASSIGNED_CITEKEY,
                         save_item_with_attachment=self.connector.save)
        self.rows = RetryRunner(FilingCompletion()).run()

    def test_the_row_reports_the_work_as_held_in_zotero(self) -> None:
        self.assertEqual((STATUS_DUPLICATE_IN_ZOTERO, ASSIGNED_CITEKEY),
                         (self.rows[0]["status"], self.rows[0]["held_as"]))

    def test_no_second_record_is_created(self) -> None:
        self.assertEqual(0, self.connector.calls)


class CitekeyHeldByAnotherWorkHttp(FakeHttp):
    def __init__(self) -> None:
        super().__init__({})

    def post(self, url: str, headers: dict = None, json: dict = None,
             data: bytes = None, timeout: float = None) -> FakeResponse:
        return FakeResponse({"result": [{"citekey": CITEKEY, "title": "Another Work"}]})


class TestBetterBibtexMatchesACitekeyToItsTitledRecord(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stub_zotero(requests=CitekeyHeldByAnotherWorkHttp())

    def test_the_record_under_the_citekey_answers_for_its_own_title(self) -> None:
        self.assertTrue(zotero.holds_titled_record(CITEKEY, "Another Work"))

    def test_the_record_under_the_citekey_does_not_answer_for_another_title(self) -> None:
        self.assertFalse(zotero.holds_titled_record(CITEKEY, "A Work"))


class TitledHoldings:
    def __init__(self, held_title: str) -> None:
        self._held_title = held_title
        self.asked: list[tuple[str, str]] = []

    def holds(self, citekey: str, title: str) -> bool:
        self.asked.append((citekey, title))
        return title == self._held_title


class CountingRefusal:
    def __init__(self) -> None:
        self.calls = 0

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self.calls += 1
        return ConnectorResult.refused()


PENDING_TITLED_CARD = (f"---\ncitekey: {CITEKEY}\nfiled: false\nzotero:\n  title: A Work\n  date: '2020'\n"
                       f"{RECORDED_CREATORS}---\n")


class TestRetryNeverAdoptsAnotherWorksRecordUnderItsCitekey(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(PENDING_TITLED_CARD)
        self.holdings = TitledHoldings("Another Work")
        self.connector = CountingRefusal()
        self.stub_zotero(is_online=lambda timeout=None: True,
                         holds_titled_record=self.holdings.holds,
                         find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         save_item_with_attachment=self.connector.save)
        RetryRunner(FilingCompletion()).run()

    def test_the_record_under_the_citekey_is_asked_for_the_cards_title(self) -> None:
        self.assertEqual([(CITEKEY, "A Work")], self.holdings.asked)

    def test_a_record_of_another_title_is_not_taken_for_the_cards_own(self) -> None:
        self.assertEqual(1, self.connector.calls)


class TestRetryAwaitsPlacementOfTheCardsOwnRecord(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(PENDING_TITLED_CARD)
        placed = self.vault.library / VERIFIED_PDF_NAME
        placed.write_bytes(PDF_BYTES)
        self.connector = CountingRefusal()
        self.stub_zotero(is_online=lambda timeout=None: True,
                         holds_titled_record=TitledHoldings("A Work").holds,
                         get_attachments=lambda citekey: [{"path": str(placed), "open": ATTACHMENT_LINK}],
                         find_existing_citekey=lambda title, doi=None, isbn=None: None,
                         save_item_with_attachment=self.connector.save)
        self.rows = RetryRunner(FilingCompletion()).run()

    def test_a_record_carrying_the_cards_title_is_not_created_again(self) -> None:
        self.assertEqual(0, self.connector.calls)


if __name__ == "__main__":
    unittest.main()
