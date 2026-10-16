from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import zotero
from zotero import ConnectorResult
from _file.filing import (
    STATUS_DUPLICATE_IN_ZOTERO,
    STATUS_ZOTERO_OFFLINE,
    Filer,
    FilingCompletion,
)
from _file_fixtures import (
    ASSIGNED_CITEKEY,
    CREDITED_DRAFT_CARD,
    INBOX_PDF_NAME,
    RECORDED_CREATORS,
    RECORDED_ISBN,
    VaultTestCase,
)
from _vaults import TextPdf
from _file_filing_fixtures import (
    FakeResponse,
    FakeHttp,
)

JSON_RPC_INTERNAL_ERROR = -32603
IDENTIFIED_DOI = "10.1/x"


class HoldingsQuestions:
    def __init__(self, held_citekey: str | None) -> None:
        self._held_citekey = held_citekey
        self.asked: list[tuple] = []

    def find(self, query: zotero.HeldWorkQuery) -> str | None:
        self.asked.append((query.title, query.doi, query.isbn))
        return self._held_citekey


class TestZoteroAlreadyHoldsTheWork(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.inbox_pdf = TextPdf(self.vault.inbox / INBOX_PDF_NAME, pages=1).write()
        self.draft_card(CREDITED_DRAFT_CARD)

    def _filed(self, held_citekey: str | None) -> dict:
        self.questions = HoldingsQuestions(held_citekey)
        self.stub_zotero(find_existing_citekey=self.questions.find,
                         save_item_with_attachment=lambda item, pdf: ConnectorResult.offline())
        return Filer(FilingCompletion()).file(self.inbox_pdf)

    def test_a_work_better_bibtex_already_holds_is_refused(self) -> None:
        self.assertEqual(STATUS_DUPLICATE_IN_ZOTERO, self._filed(ASSIGNED_CITEKEY)["status"])

    def test_the_found_citekey_is_reported(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY, self._filed(ASSIGNED_CITEKEY)["held_as"])

    def test_the_identified_doi_is_asked_for_too(self) -> None:
        self.draft_card(f"---\nidentified:\n  identifier:\n    kind: doi\n    value: {IDENTIFIED_DOI}\n"
                        f"zotero:\n{RECORDED_CREATORS}---\n")
        self._filed(None)
        self.assertEqual(IDENTIFIED_DOI, self.questions.asked[0][1])

    def test_the_recorded_isbn_is_asked_for_too(self) -> None:
        self.draft_card(f"---\nzotero:\n  ISBN: '{RECORDED_ISBN}'\n{RECORDED_CREATORS}---\n")
        self._filed(None)
        self.assertEqual(RECORDED_ISBN, self.questions.asked[0][2])

    def test_an_identified_isbn_is_asked_for_when_none_is_recorded(self) -> None:
        self.draft_card(f"---\nidentified:\n  identifier:\n    kind: isbn\n    value: '{RECORDED_ISBN}'\n"
                        f"zotero:\n{RECORDED_CREATORS}---\n")
        self._filed(None)
        self.assertEqual(RECORDED_ISBN, self.questions.asked[0][2])

    def test_an_unheld_work_is_filed(self) -> None:
        self.assertEqual(STATUS_ZOTERO_OFFLINE, self._filed(None)["status"])


class IsbnAnsweringHttp(FakeHttp):
    def __init__(self) -> None:
        super().__init__({})

    def post(self, url: str, headers: dict = None, json: dict = None,
             data: bytes = None, timeout: float = None) -> FakeResponse:
        [[condition]] = (json or {}).get("params", [[[None]]])
        held = [{"citekey": ASSIGNED_CITEKEY, "title": "A Work, Second Edition"}]
        return FakeResponse({"result": held if condition == ["ISBN", "contains", RECORDED_ISBN] else []})


class RefusingSearchHttp(FakeHttp):
    def __init__(self) -> None:
        super().__init__({})

    def post(self, url: str, headers: dict = None, json: dict = None,
             data: bytes = None, timeout: float = None) -> FakeResponse:
        error = {"code": JSON_RPC_INTERNAL_ERROR, "message": "Invalid condition 'blockStart'"}
        return FakeResponse({"error": error})


class TestBetterBibtexFindsAHeldWorkByIsbn(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stub_zotero(requests=IsbnAnsweringHttp())

    def test_a_reworded_second_edition_is_found_by_its_isbn_condition(self) -> None:
        self.assertEqual(ASSIGNED_CITEKEY,
                         zotero.find_existing_citekey(zotero.HeldWorkQuery("A Work", isbn=RECORDED_ISBN)))

    def test_without_the_isbn_the_reworded_title_is_not_found(self) -> None:
        self.assertIsNone(zotero.find_existing_citekey(zotero.HeldWorkQuery("A Work")))


class HeldRecordsHttp(FakeHttp):
    def __init__(self, held: list[dict]) -> None:
        super().__init__({})
        self._held = held

    def post(self, url: str, headers: dict = None, json: dict = None,
             data: bytes = None, timeout: float = None) -> FakeResponse:
        [[[field, _, value]]] = (json or {}).get("params")
        return FakeResponse({"result": [item for item in self._held if value in str(item.get(field, ""))]})


def held_record(item_type: str, family: str, isbn: str = "") -> dict:
    return {"citekey": ASSIGNED_CITEKEY, "type": item_type, "title": "A Work", "ISBN": isbn,
            "author": [{"family": family}]}


class TestADifferentWorkSharingATitleOrABookIsNotADuplicate(VaultTestCase):
    def _held_as(self, held: list[dict], query: zotero.HeldWorkQuery) -> str | None:
        self.stub_zotero(requests=HeldRecordsHttp(held))
        return zotero.find_existing_citekey(query)

    def test_a_work_by_another_author_under_the_same_title_is_not_held(self) -> None:
        held = [held_record("chapter", "Other")]
        self.assertIsNone(self._held_as(held, zotero.HeldWorkQuery("A Work", first_creator="Doe")))

    def test_the_same_title_by_the_same_author_is_held(self) -> None:
        held = [held_record("chapter", "Doe")]
        self.assertEqual(ASSIGNED_CITEKEY, self._held_as(held, zotero.HeldWorkQuery("A Work", first_creator="Doe")))

    def test_a_chapter_sharing_its_anthology_isbn_with_a_held_chapter_is_not_held(self) -> None:
        held = [held_record("chapter", "Other", RECORDED_ISBN)]
        query = zotero.HeldWorkQuery("Another Chapter", isbn=RECORDED_ISBN, first_creator="Doe", chapter=True)
        self.assertIsNone(self._held_as(held, query))

    def test_a_book_is_not_held_by_a_chapter_carrying_its_isbn(self) -> None:
        held = [held_record("chapter", "Other", RECORDED_ISBN)]
        self.assertIsNone(self._held_as(held, zotero.HeldWorkQuery("A Book", isbn=RECORDED_ISBN)))

    def test_a_book_held_under_its_isbn_is_held(self) -> None:
        held = [held_record("book", "Doe", RECORDED_ISBN)]
        self.assertEqual(ASSIGNED_CITEKEY, self._held_as(held, zotero.HeldWorkQuery("A Book", isbn=RECORDED_ISBN)))


class TestARefusedSearchIsNeverReadAsNotHeld(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stub_zotero(requests=RefusingSearchHttp())

    def test_the_duplicate_check_raises_when_better_bibtex_refuses_the_search(self) -> None:
        with self.assertRaises(zotero.BetterBibtexError):
            zotero.find_existing_citekey(zotero.HeldWorkQuery("A Work"))

    def test_the_item_key_lookup_raises_when_better_bibtex_refuses_the_search(self) -> None:
        with self.assertRaises(zotero.BetterBibtexError):
            zotero.get_item_key(ASSIGNED_CITEKEY)


if __name__ == "__main__":
    unittest.main()
