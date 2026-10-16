from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _file.filing import FilingCompletion
from _file.notes import CorpusNote
from _file.refile import RefileTarget, Refiler
from _file_fixtures import ATTACHMENT_LINK, PLACED_PDF_NAME, RECORDED_CREATORS, Citation, VaultTestCase
from _vaults import TextPdf

BOOK_FIELDS = "  itemType: book\n  date: '2020'\n  publisher: A Press\n  place: Cambridge\n"
UNTITLED_UNCREDITED_CARD = f"---\nzotero:\n{BOOK_FIELDS}---\n"
COMPLETE_CARD = f"---\nzotero:\n{BOOK_FIELDS}  title: A Work\n{RECORDED_CREATORS}---\n"


class RefileCompletenessTestCase(VaultTestCase):
    def refiler(self, card: str) -> Refiler:
        TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        (self.vault.inbox / Path(PLACED_PDF_NAME).with_suffix(".md").name).write_text(card, encoding="utf-8")
        return Refiler(RefileTarget(PLACED_PDF_NAME), FilingCompletion())


class TestARefileWhoseDraftCardNamesNoTitleOrCreators(RefileCompletenessTestCase):
    def setUp(self) -> None:
        super().setUp()
        with self.assertRaises(SystemExit) as refusal:
            self.refiler(UNTITLED_UNCREDITED_CARD).require_complete_bib()
        self.message = str(refusal.exception.code)

    def test_the_refusal_names_the_title(self) -> None:
        self.assertIn("'title'", self.message)

    def test_the_refusal_names_the_creators(self) -> None:
        self.assertIn("'creators'", self.message)


class TestARefileWhoseDraftCardIsComplete(RefileCompletenessTestCase):
    def test_the_refile_is_not_refused(self) -> None:
        self.refiler(COMPLETE_CARD).require_complete_bib()


if __name__ == "__main__":
    unittest.main()
