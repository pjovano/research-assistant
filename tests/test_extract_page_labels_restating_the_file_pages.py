from __future__ import annotations

import unittest

from test_extract_folio_signals import FILE_PAGE_NUMBERING, LabelledPdfCase

UNPRINTED_PAGES = 4
PRINTED_FROM_FIRST_PAGE = ["Title 1", "Title 2", "Title 3", None]


class TestFilePageLabelsWhereNoFolioPrints(LabelledPdfCase):
    HEADERS = [None] * UNPRINTED_PAGES
    LABELS = FILE_PAGE_NUMBERING

    def test_a_label_restating_the_file_page_is_no_folio(self) -> None:
        self.assertEqual([None] * UNPRINTED_PAGES, self.folios())

    def test_the_page_marker_carries_only_the_file_page(self) -> None:
        self.assertIn("%% file p. 2 %%", self.build.rendered().text)


class TestFilePageLabelsAgreeingWithPrintedFolios(LabelledPdfCase):
    HEADERS = PRINTED_FROM_FIRST_PAGE
    LABELS = FILE_PAGE_NUMBERING

    def test_a_page_printing_no_folio_takes_the_label_the_printed_folios_agree_with(self) -> None:
        self.assertEqual(["1", "2", "3", "4"], self.folios())


if __name__ == "__main__":
    unittest.main()
