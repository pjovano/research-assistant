from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from zotero import BetterBibtexError, ConnectorResult
from _file.filing import FilingAttempt, FilingCompletion
from _file.notes import CorpusNote, DraftCard
from _file.preview import FilingPreview
from _file.retry import RetryRunner
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    ATTACHMENT_LINK,
    CITEKEY,
    INBOX_PDF_NAME,
    PDF_BYTES,
    RECORDED_CREATORS,
    ZOTERO_ITEM_KEY,
    Citation,
    VaultTestCase,
    saved_with_key,
)
from _vaults import TextPdf


def better_bibtex_offline(*arguments) -> None:
    raise BetterBibtexError("Better BibTeX item.search failed: connection refused")


class TestARecordSavedBeforeBetterBibtexGoesOffline(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        source = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.stub_zotero(save_item_with_attachment=lambda item, pdf: saved_with_key(),
                         get_citation_key=better_bibtex_offline,
                         find_existing_citekey=better_bibtex_offline)
        with self.assertRaises(BetterBibtexError):
            FilingAttempt(DraftCard(INBOX_PDF_NAME).load(), source, Citation().meta()).file()
        self.card = DraftCard(INBOX_PDF_NAME).load()

    def test_the_draft_card_is_marked_filed(self) -> None:
        self.assertTrue(self.card.filed)

    def test_the_draft_card_keeps_the_item_key_zotero_returned(self) -> None:
        self.assertEqual(ZOTERO_ITEM_KEY, self.card.item_key)


class AttachmentPolls:
    def __init__(self, placed: Path) -> None:
        self._placed = placed
        self.citekeys: list[str] = []

    def attachments(self, citekey: str) -> list[dict]:
        self.citekeys.append(citekey)
        return [{"path": str(self._placed), "open": ATTACHMENT_LINK}]


class RefusingConnector:
    def __init__(self) -> None:
        self.calls = 0

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self.calls += 1
        return ConnectorResult.refused()


FILED_CARD_WITH_ITEM_KEY = (f"---\ncitekey: {CITEKEY}\nfiled: true\nitem_key: {ZOTERO_ITEM_KEY}\n"
                            f"zotero:\n  title: A Work\n  date: '2020'\n{RECORDED_CREATORS}---\n")


class TestRetryOfACardFiledBeforeItsCitekeyWasRead(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        source = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(FILED_CARD_WITH_ITEM_KEY)
        placed = self.vault.library / FilingPreview.of(source).library_filename()
        placed.write_bytes(PDF_BYTES)
        self.placed_name = placed.name
        self.polls = AttachmentPolls(placed)
        self.connector = RefusingConnector()
        self.stub_zotero(is_online=lambda timeout=None: True,
                         get_citation_key=lambda item_key: ASSIGNED_CITEKEY if item_key == ZOTERO_ITEM_KEY else None,
                         get_attachments=self.polls.attachments,
                         find_existing_citekey=lambda query: ASSIGNED_CITEKEY,
                         save_item_with_attachment=self.connector.save)
        self.rows = RetryRunner(FilingCompletion()).run()

    def test_the_placement_is_awaited_under_the_citekey_of_the_stored_item(self) -> None:
        self.assertEqual({ASSIGNED_CITEKEY}, set(self.polls.citekeys))

    def test_the_work_is_not_reported_as_a_duplicate_of_its_own_record(self) -> None:
        self.assertNotEqual("duplicate-in-zotero", self.rows[0]["status"])

    def test_no_second_record_is_created(self) -> None:
        self.assertEqual(0, self.connector.calls)

    def test_the_corpus_file_records_the_citekey_zotero_assigned(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, CorpusNote(self.placed_name).fields()["citekey"])


if __name__ == "__main__":
    unittest.main()
