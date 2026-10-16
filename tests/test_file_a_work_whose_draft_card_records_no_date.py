from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import pymupdf
from _file.bib import RequiredFields
from _file.preview import FilingPreview
from _file.probe import PdfProbe
from _file_fixtures import CREDITED_DRAFT_CARD, INBOX_PDF_NAME, VaultTestCase

SCAN_DATE = "D:20190401120000Z"
COMPLETE_BOOK_FIELDS = {"publisher": "A Press", "place": "Cambridge"}


class TestAPdfWhoseOnlyYearIsItsCreationDate(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.path = self.pdf(INBOX_PDF_NAME).write()
        self.draft_card(CREDITED_DRAFT_CARD)
        with pymupdf.open(self.path) as doc:
            doc.set_metadata({"creationDate": SCAN_DATE})
            doc.saveIncr()

    def test_the_probe_takes_no_year_from_the_creation_date(self) -> None:
        self.assertEqual("", PdfProbe().of(self.path)["year"])

    def test_the_predicted_name_is_undated(self) -> None:
        self.assertIn(" - n.d. - ", FilingPreview.of(self.path).library_filename())


class TestAMissingDateIsAMissingField(unittest.TestCase):
    def test_a_book_without_a_date_lists_the_date(self) -> None:
        self.assertEqual(["date"], RequiredFields().missing("book", COMPLETE_BOOK_FIELDS))

    def test_a_book_with_a_date_lists_nothing(self) -> None:
        self.assertEqual([], RequiredFields().missing("book", {**COMPLETE_BOOK_FIELDS, "date": "2019"}))

    def test_a_type_with_no_other_required_field_lists_the_date(self) -> None:
        self.assertEqual(["date"], RequiredFields().missing("manuscript", {}))


if __name__ == "__main__":
    unittest.main()
