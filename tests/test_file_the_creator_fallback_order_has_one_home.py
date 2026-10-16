from __future__ import annotations

import unittest
from http import HTTPStatus
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import requests
import zotero
from _file.bib import MetadataMerge
from _file.notes import DraftCard
from _file.records import CslRecord
from _file_fixtures import ASSIGNED_CITEKEY, INBOX_PDF_NAME, VaultTestCase

TRANSLATOR_FIRST = ("translator", "editor", "author")
CARD_WITH_AUTHOR_AND_TRANSLATOR = (
    "---\nzotero:\n  creators:\n"
    "  - {creatorType: author, firstName: Ann, lastName: Writer}\n"
    "  - {creatorType: translator, firstName: Tom, lastName: Turner}\n---\n")
CSL_WITH_AUTHOR_AND_TRANSLATOR = {"author": [{"family": "Writer", "given": "Ann"}],
                                  "translator": [{"family": "Turner", "given": "Tom"}]}


class Answer:
    def __init__(self, body: dict) -> None:
        self.status_code = HTTPStatus.OK
        self._body = body

    def json(self) -> dict:
        return self._body


class HeldTranslation:
    RequestException = requests.RequestException

    def post(self, url: str, json: dict = None, timeout: float = None) -> Answer:
        return Answer({"result": [{"citekey": ASSIGNED_CITEKEY, "title": "A Work", **CSL_WITH_AUTHOR_AND_TRANSLATOR}]})


class TestEveryReaderFollowsTheOneFallbackOrder(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        patch = mock.patch.object(zotero, "CREATOR_FALLBACK_ORDER", TRANSLATOR_FIRST)
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_draft_card_merge_takes_the_first_role_of_the_order(self) -> None:
        self.draft_card(CARD_WITH_AUTHOR_AND_TRANSLATOR)
        meta = {"title": "A Work", "authors": [], "year": "", "type": "book"}
        MetadataMerge().into(meta, DraftCard(INBOX_PDF_NAME).load())
        self.assertEqual(["Turner"], [author["lastName"] for author in meta["authors"]])

    def test_a_better_bibtex_record_takes_the_first_role_of_the_order(self) -> None:
        meta = CslRecord(CSL_WITH_AUTHOR_AND_TRANSLATOR).meta()
        self.assertEqual(["Turner"], [author["lastName"] for author in meta["authors"]])

    def test_the_held_work_search_takes_the_first_role_of_the_order(self) -> None:
        self.stub_zotero(requests=HeldTranslation())
        query = zotero.HeldWorkQuery("A Work", first_creator="Turner")
        self.assertEqual(ASSIGNED_CITEKEY, zotero.find_existing_citekey(query))


if __name__ == "__main__":
    unittest.main()
