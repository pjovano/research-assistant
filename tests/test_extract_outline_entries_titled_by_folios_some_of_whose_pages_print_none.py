from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.outline import Outline

PAGE_COUNT = 4
FIRST_FOLIO = 102
UNNUMBERED_FILE_PAGES = {1, 3}
PROSE = "The argument of the work runs on across this page."


class PartlyLabelledPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "partly-labelled.pdf"

    def with_outline(self, toc: list, unnumbered_pages: set[int]) -> Path:
        with pymupdf.open() as document:
            for _ in range(PAGE_COUNT):
                document.new_page().insert_text((72, 300), PROSE)
            document.set_page_labels([self._label_range(page, unnumbered_pages) for page in range(1, PAGE_COUNT + 1)])
            document.set_toc(toc)
            document.save(self._path)
        return self._path

    @staticmethod
    def _label_range(file_page: int, unnumbered_pages: set[int]) -> dict:
        if file_page in unnumbered_pages:
            return {"startpage": file_page - 1, "prefix": "", "style": "", "firstpagenum": 1}
        return {"startpage": file_page - 1, "prefix": "", "style": "D", "firstpagenum": FIRST_FOLIO + file_page - 1}


def folio_titled_entries() -> list:
    return [[1, str(FIRST_FOLIO + page - 1), page] for page in range(1, PAGE_COUNT + 1)]


class TestOutlineEntriesTitledByFoliosSomeOfWhosePagesPrintNone(unittest.TestCase):
    def _titles(self, toc: list, unnumbered_pages: set[int]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            pdf = PartlyLabelledPdf(directory).with_outline(toc, unnumbered_pages)
            return [heading.title for heading in Outline(pdf).headings()]

    def test_folio_entries_carry_no_division_where_some_of_their_pages_print_no_folio(self) -> None:
        self.assertEqual([], self._titles(folio_titled_entries(), UNNUMBERED_FILE_PAGES))

    def test_numerals_of_which_only_one_page_prints_a_folio_keep_their_headings(self) -> None:
        toc = folio_titled_entries()
        unnumbered_but_the_first = set(range(2, PAGE_COUNT + 1))
        self.assertEqual([title for _level, title, _page in toc], self._titles(toc, unnumbered_but_the_first))


if __name__ == "__main__":
    unittest.main()
