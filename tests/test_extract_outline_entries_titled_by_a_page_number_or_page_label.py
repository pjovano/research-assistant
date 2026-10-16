from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.outline import Outline

PAGE_COUNT = 4
FIRST_ARABIC_FOLIO = 166
FIRST_ROMAN_FOLIO = 3
SECTION_TITLE = "The Problem of Reference"
SECTION_PAGE = 3
FAR_SECTION_NUMERALS = ["I", "II"]
FIRST_FOLIO_OF_A_WORK = 1
SECTIONS_ONE_MEETING_ITS_FOLIO = [[1, "I", 1], [1, "II", 4]]
PROSE = "The argument of the work runs on across this page."


class LabelledPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "labelled.pdf"

    def with_outline(self, toc: list, style: str = "D", first_folio: int = FIRST_ARABIC_FOLIO) -> Path:
        with pymupdf.open() as document:
            for _ in range(PAGE_COUNT):
                document.new_page().insert_text((72, 300), PROSE)
            document.set_page_labels([{"startpage": 0, "prefix": "", "style": style, "firstpagenum": first_folio}])
            document.set_toc(toc)
            document.save(self._path)
        return self._path


def one_entry_per_page(title_of) -> list:
    return [[1, title_of(page), page] for page in range(1, PAGE_COUNT + 1)]


class TestOutlineEntriesTitledByAPageNumberOrPageLabel(unittest.TestCase):
    def _titles(self, toc: list, **labels) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            return [heading.title for heading in Outline(LabelledPdf(directory).with_outline(toc, **labels)).headings()]

    def test_entries_titled_as_page_references_carry_no_division(self) -> None:
        toc = one_entry_per_page(lambda page: f"p. {FIRST_ARABIC_FOLIO + page - 1}")
        self.assertEqual([], self._titles(toc))

    def test_entries_titled_by_the_folio_of_their_page_carry_no_division(self) -> None:
        toc = one_entry_per_page(lambda page: str(FIRST_ARABIC_FOLIO + page - 1))
        self.assertEqual([], self._titles(toc))

    def test_entries_titled_by_a_folio_one_off_their_page_carry_no_division(self) -> None:
        toc = [[1, str(FIRST_ARABIC_FOLIO), 1], [1, str(FIRST_ARABIC_FOLIO + 1), 1]]
        self.assertEqual([], self._titles(toc))

    def test_entries_titled_by_the_roman_label_of_their_page_carry_no_division(self) -> None:
        romans = ["iii", "iv", "v", "vi"]
        toc = one_entry_per_page(lambda page: romans[page - 1])
        self.assertEqual([], self._titles(toc, style="r", first_folio=FIRST_ROMAN_FOLIO))

    def test_a_titled_entry_beside_page_entries_keeps_its_heading(self) -> None:
        toc = sorted(one_entry_per_page(lambda page: f"p. {FIRST_ARABIC_FOLIO + page - 1}")
                     + [[1, SECTION_TITLE, SECTION_PAGE]], key=lambda entry: entry[2])
        self.assertEqual([SECTION_TITLE], self._titles(toc))

    def test_an_entry_titled_by_a_bracketed_page_reference_carries_no_division(self) -> None:
        toc = one_entry_per_page(lambda page: f"p. [{FIRST_ARABIC_FOLIO + page - 1}]")
        self.assertEqual([], self._titles(toc))

    def test_section_numerals_of_which_one_meets_the_folio_of_its_page_keep_their_headings(self) -> None:
        titles = self._titles(SECTIONS_ONE_MEETING_ITS_FOLIO, first_folio=FIRST_FOLIO_OF_A_WORK)
        self.assertEqual([title for _level, title, _page in SECTIONS_ONE_MEETING_ITS_FOLIO], titles)

    def test_section_numerals_far_from_the_folios_of_their_pages_keep_their_headings(self) -> None:
        toc = [[1, numeral, page] for page, numeral in enumerate(FAR_SECTION_NUMERALS, start=1)]
        self.assertEqual(FAR_SECTION_NUMERALS, self._titles(toc))


if __name__ == "__main__":
    unittest.main()
