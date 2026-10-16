from __future__ import annotations

import time
import unittest

from _support import LiveTree

LiveTree.activate()

import zotero
from zotero import ConnectorResult
from _file.notes import DraftCard
from _file.filing import (
    AssignedCitekey,
    FilingAttempt,
)
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    ATTACHMENT_LINK,
    CITEKEY,
    INBOX_PDF_NAME,
    PDF_BYTES,
    PLACED_PDF_NAME,
    ZOTERO_ITEM_KEY,
    Citation,
    VaultTestCase,
    saved_with_key,
)
from _file_filing_fixtures import (
    FakeResponse,
    FakeHttp,
)


class TestTheConnectorReportsTheItemKey(VaultTestCase):
    def _result(self, saved_body: dict) -> ConnectorResult:
        pdf = self.vault.inbox / INBOX_PDF_NAME
        pdf.write_bytes(PDF_BYTES)
        self.stub_zotero(requests=FakeHttp(saved_body))
        return zotero.save_item_with_attachment(Citation().meta(), pdf)

    def test_the_key_zotero_returned_is_carried_on_the_result(self) -> None:
        self.assertEqual(ZOTERO_ITEM_KEY, self._result({"items": [{"key": ZOTERO_ITEM_KEY}]}).item_key)

    def test_a_response_naming_no_key_leaves_the_result_without_one(self) -> None:
        self.assertIsNone(self._result({"items": [{"title": "A Work"}]}).item_key)


class RecordingHttp(FakeHttp):
    def __init__(self) -> None:
        super().__init__({"items": [{"key": ZOTERO_ITEM_KEY}]})
        self.posts: list[tuple[str, dict | None]] = []

    def post(self, url: str, headers: dict = None, json: dict = None,
             data: bytes = None, timeout: float = None) -> FakeResponse:
        self.posts.append((url, json))
        return super().post(url, headers, json, data, timeout)


class TestTheConnectorSavesABareItem(VaultTestCase):
    RECORDING = "https://www.youtube.com/watch?v=abc123"

    def setUp(self) -> None:
        super().setUp()
        self.http = RecordingHttp()
        self.stub_zotero(requests=self.http)
        self.result = zotero.save_item({**Citation().meta(), "creator_type": "presenter"}, self.RECORDING)

    def test_the_item_is_saved_under_the_recording_uri_and_nothing_is_attached(self) -> None:
        [(url, payload)] = self.http.posts
        self.assertTrue(url.endswith("/connector/saveItems"))
        self.assertEqual(self.RECORDING, payload["uri"])

    def test_the_result_carries_the_key_and_no_attachment(self) -> None:
        self.assertEqual((True, False, ZOTERO_ITEM_KEY),
                         (self.result.item_saved, self.result.attachment_saved, self.result.item_key))

    def test_the_creators_take_the_creator_type_the_meta_names(self) -> None:
        [(_url, payload)] = self.http.posts
        self.assertEqual({"presenter"}, {creator["creatorType"] for creator in payload["items"][0]["creators"]})


class TestAssignedCitekey(VaultTestCase):
    def _assigned(self, result: ConnectorResult, **stubs) -> str:
        self.stub_zotero(**stubs)
        return AssignedCitekey(CITEKEY).after(result, Citation().meta())

    def test_the_citation_key_of_the_returned_item_wins(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self._assigned(
            saved_with_key(),
            get_citation_key=lambda item_key: ASSIGNED_CITEKEY,
            find_existing_citekey=lambda title, doi=None: None))

    def test_without_an_item_key_better_bibtex_is_asked_for_the_title(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self._assigned(
            ConnectorResult.saved(),
            find_existing_citekey=lambda title, doi=None: ASSIGNED_CITEKEY))

    def test_an_unreachable_better_bibtex_leaves_the_predicted_key(self) -> None:
        self.assertEqual(CITEKEY, self._assigned(
            ConnectorResult.saved(),
            find_existing_citekey=lambda title, doi=None: None))


class CitationKeyAssignedLate:
    def __init__(self, unanswered_reads: int) -> None:
        self._unanswered_reads = unanswered_reads

    def citation_key(self, item_key: str) -> str | None:
        if self._unanswered_reads:
            self._unanswered_reads -= 1
            return None
        return ASSIGNED_CITEKEY


class TestACitationKeyBetterBibtexAssignsLateIsAwaited(VaultTestCase):
    def test_the_key_assigned_after_the_first_read_wins_over_the_title_search(self) -> None:
        self.stub_zotero(get_citation_key=CitationKeyAssignedLate(1).citation_key,
                         find_existing_citekey=lambda title, doi=None: f"{CITEKEY}z")
        self.stub_sleep()
        self.assertEqual(ASSIGNED_CITEKEY, AssignedCitekey(CITEKEY).after(saved_with_key(), Citation().meta()))

    def stub_sleep(self) -> None:
        self.addCleanup(setattr, time, "sleep", time.sleep)
        time.sleep = lambda seconds: None


class PollRecorder:
    def __init__(self, attachment: dict) -> None:
        self._attachment = attachment
        self.citekey_polled: str | None = None
        self.citekey_on_card: str | None = None

    def attachments(self, citekey: str) -> list[dict]:
        self.citekey_polled = citekey
        self.citekey_on_card = DraftCard(INBOX_PDF_NAME).load().citekey
        return [self._attachment]


class TestTheAssignedCitekeyIsRecordedBeforeThePoll(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.source_pdf = self.vault.inbox / INBOX_PDF_NAME
        self.source_pdf.write_bytes(PDF_BYTES)
        placed = self.vault.library / PLACED_PDF_NAME
        placed.write_bytes(PDF_BYTES)
        self.recorder = PollRecorder({"path": str(placed), "open": ATTACHMENT_LINK})
        self.stub_zotero(
            save_item_with_attachment=lambda item, pdf: saved_with_key(),
            get_citation_key=lambda item_key: ASSIGNED_CITEKEY,
            get_attachments=self.recorder.attachments)
        attempt = FilingAttempt(DraftCard(INBOX_PDF_NAME).load(), self.source_pdf, Citation().meta())
        attempt.file()
        self.outcome = attempt.outcome()

    def test_the_outcome_is_not_asked_for_before_the_attempt(self) -> None:
        with self.assertRaises(RuntimeError):
            FilingAttempt(DraftCard(INBOX_PDF_NAME).load(), self.source_pdf, Citation().meta()).outcome()

    def test_the_outcome_carries_the_key_zotero_assigned(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self.outcome.citekey)

    def test_the_placement_is_polled_under_the_key_zotero_assigned(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self.recorder.citekey_polled)

    def test_the_draft_card_carries_that_key_before_the_poll(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self.recorder.citekey_on_card)


if __name__ == "__main__":
    unittest.main()
