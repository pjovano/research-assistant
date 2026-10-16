from __future__ import annotations

import unittest
from http import HTTPStatus
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import requests
import zotero
from zotero import BetterBibtexError
from _file.notes import CorpusNote
from _file.records import STATUS_RECORD_UNREADABLE, FiledRecordNote, ZoteroDatabase
from _file.relink import Relinker
from _file_fixtures import ATTACHMENT_LINK, CITEKEY, PLACED_PDF_NAME, ZOTERO_ITEM_KEY, Citation, VaultTestCase
from _vaults import TextPdf

JSON_RPC_INTERNAL_ERROR = -32603


class Answer:
    def __init__(self, body: dict) -> None:
        self.status_code = HTTPStatus.OK
        self._body = body

    def json(self) -> dict:
        return self._body


class BetterBibtexFailingAttachments:
    RequestException = requests.RequestException

    def post(self, url: str, json: dict = None, timeout: float = None) -> Answer:
        if json["method"] == "item.attachments":
            return Answer({"error": {"code": JSON_RPC_INTERNAL_ERROR, "message": "attachments unavailable"}})
        return Answer({"result": [{"citekey": CITEKEY, "id": f"http://zotero.org/users/1/items/{ZOTERO_ITEM_KEY}"}]})


class TestAPdfLinkWhoseAttachmentLookupFails(VaultTestCase):
    def test_the_failure_is_raised_instead_of_a_select_link(self) -> None:
        self.stub_zotero(requests=BetterBibtexFailingAttachments())
        with self.assertRaises(BetterBibtexError):
            zotero.build_pdf_link(CITEKEY)


def failing_link(citekey: str) -> str:
    raise BetterBibtexError("Better BibTeX item.attachments failed: attachments unavailable")


class TestRelinkOfACorpusFileWhoseLinkLookupFails(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.stub_zotero(build_pdf_link=failing_link)
        relinker = Relinker([PLACED_PDF_NAME])
        self.rows = relinker.rows()
        relinker.write(self.rows)

    def test_the_row_reports_the_failed_lookup(self) -> None:
        self.assertEqual(["lookup-failed"], [row.action for row in self.rows])

    def test_the_link_is_left_as_it_was(self) -> None:
        self.assertEqual(ATTACHMENT_LINK, CorpusNote(PLACED_PDF_NAME).link())


class TestANoteWhoseLinkLookupFails(VaultTestCase):
    def test_the_note_reports_the_record_unreadable(self) -> None:
        pdf = TextPdf(self.vault.library / PLACED_PDF_NAME).write()
        self.stub_zotero(is_online=lambda timeout=None: True, get_citation_key=lambda item_key: CITEKEY,
                         build_pdf_link=failing_link)
        with mock.patch.object(ZoteroDatabase, "parent_item_key", return_value=ZOTERO_ITEM_KEY):
            self.assertEqual(STATUS_RECORD_UNREADABLE, FiledRecordNote(pdf).preview()["status"])


if __name__ == "__main__":
    unittest.main()
