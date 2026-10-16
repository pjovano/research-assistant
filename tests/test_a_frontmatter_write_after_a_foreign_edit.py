from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import vault
from _file.notes import CorpusNote, DraftCard
from _file.records import FiledRecordNote, ZoteroDatabase
from _file_fixtures import (
    ATTACHMENT_LINK,
    CITEKEY,
    DATED_DRAFT_CARD,
    INBOX_PDF_NAME,
    PLACED_PDF_NAME,
    ZOTERO_ITEM_KEY,
    Citation,
    VaultTestCase,
)
from _vaults import TextPdf

FOREIGN_TEXT = "---\ntitle: Written by hand meanwhile\n---\n"
CSL_BOOK = {"type": "book", "title": "A Work", "author": [{"family": "Doe"}], "issued": {"date-parts": [[2020]]}}


class TestADraftCardEditedBetweenItsReadAndItsSave(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.card = self.draft_card(DATED_DRAFT_CARD)
        draft = DraftCard(INBOX_PDF_NAME).load()
        self.card.write_text(FOREIGN_TEXT, encoding="utf-8")
        draft.adopt(Citation().meta(), CITEKEY)
        with self.assertRaises(vault.NoteChangedOnDisk):
            draft.save()

    def test_the_foreign_edit_survives(self) -> None:
        self.assertEqual(FOREIGN_TEXT, self.card.read_text(encoding="utf-8"))


class TestADraftCardCreatedBetweenItsReadAndItsSave(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        draft = DraftCard(INBOX_PDF_NAME).load()
        self.card = self.draft_card(FOREIGN_TEXT)
        draft.adopt(Citation().meta(), CITEKEY)
        with self.assertRaises(vault.NoteChangedOnDisk):
            draft.save()

    def test_the_foreign_card_survives(self) -> None:
        self.assertEqual(FOREIGN_TEXT, self.card.read_text(encoding="utf-8"))


class TestADraftCardSavedTwiceWithoutAForeignEdit(VaultTestCase):
    def test_the_second_save_is_written(self) -> None:
        draft = DraftCard(INBOX_PDF_NAME).load()
        draft.adopt(Citation().meta(), CITEKEY)
        draft.save()
        draft.adopt(Citation().meta(), f"{CITEKEY}a")
        draft.save()
        self.assertEqual(f"{CITEKEY}a", DraftCard(INBOX_PDF_NAME).load().citekey)


class CorpusFileWrittenDuringTheLookup:
    def __init__(self, note: CorpusNote) -> None:
        self._note = note

    def record(self, citekey: str) -> dict:
        self._note.path.write_text(FOREIGN_TEXT, encoding="utf-8")
        return CSL_BOOK


class TestACorpusFileWrittenWhileItsNoteIsPlanned(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        pdf = TextPdf(self.vault.library / PLACED_PDF_NAME).write()
        self.note = CorpusNote(PLACED_PDF_NAME)
        self.stub_zotero(is_online=lambda timeout=None: True, get_citation_key=lambda item_key: CITEKEY,
                         build_pdf_link=lambda citekey: ATTACHMENT_LINK,
                         get_csl_record=CorpusFileWrittenDuringTheLookup(self.note).record)
        with mock.patch.object(ZoteroDatabase, "parent_item_key", return_value=ZOTERO_ITEM_KEY), \
                self.assertRaises(vault.NoteChangedOnDisk):
            FiledRecordNote(pdf).write()

    def test_the_foreign_corpus_file_survives(self) -> None:
        self.assertEqual(FOREIGN_TEXT, self.note.path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
