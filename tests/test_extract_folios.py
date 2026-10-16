from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BBOX, FakeLayer
from _extract.blocks import Block, PageBlocks
from _extract.pagefolios import FolioReader

PAGE_HEADER_KIND = "PageHeader"
PRINTED_OFFSET = 382
LABEL_OFFSET = 38


class LabelledLayer(FakeLayer):
    def label(self, file_page: int) -> str | None:
        return str(file_page + LABEL_OFFSET)


def furnished_page(file_page: int, texts: list[str]) -> PageBlocks:
    blocks = [Block(file_page, PAGE_HEADER_KIND, f"<p>{text}</p>", BBOX, {},
                    f"/page/{file_page}/{PAGE_HEADER_KIND}/{index}") for index, text in enumerate(texts)]
    return PageBlocks(file_page, blocks)


def printed_run(first_page: int, last_page: int) -> list[list[str]]:
    return [[str(page + PRINTED_OFFSET)] for page in range(first_page, last_page)]


class TestFolioReader(unittest.TestCase):
    def _folios(self, furniture: list[list[str]], layer=None) -> list:
        pages = [furnished_page(number, texts) for number, texts in enumerate(furniture, start=1)]
        return list(FolioReader(layer or FakeLayer()).of(pages).values())

    def test_a_trailing_number_in_a_running_head_is_the_folio_once_the_pages_agree(self) -> None:
        heads = [[f"Presuppositionless Thinking {folio}"] for folio in (39, 40, 41)]
        self.assertEqual(["39", "40", "41"], self._folios(heads))

    def test_a_leading_number_is_the_folio_even_before_a_roman_chapter_number(self) -> None:
        heads = [[f"{folio} III Semantics of First-Order Languages"] for folio in (32, 33, 34)]
        self.assertEqual(["32", "33", "34"], self._folios(heads))

    def test_a_bare_roman_numeral_is_a_folio(self) -> None:
        self.assertEqual(["xiv"], self._folios([["xiv"]]))

    def test_a_bare_word_of_roman_letters_that_is_no_well_formed_numeral_is_not_a_folio(self) -> None:
        for word in ("did", "mill", "civil", "iiiii"):
            with self.subTest(word=word):
                self.assertEqual([None], self._folios([[word]]))

    def test_a_capitalised_roman_chapter_number_at_the_edge_is_not_a_folio(self) -> None:
        self.assertEqual([None], self._folios([["III Semantics of First-Order Languages"]]))

    def test_a_page_without_a_number_records_none(self) -> None:
        self.assertEqual([None], self._folios([["Running head only"]]))

    def test_a_year_in_the_furniture_loses_to_a_genuine_folio(self) -> None:
        heads = [["Published online June 19, 2023", "Semantics 383"], ["Semantics 384"], ["Semantics 385"]]
        self.assertEqual("383", self._folios(heads)[0])

    def test_a_year_alone_is_not_a_folio(self) -> None:
        self.assertEqual([None], self._folios([["Published online June 19, 2023"]]))

    def test_a_year_breaking_its_neighbours_run_yields_no_folio(self) -> None:
        self.assertEqual(None, self._folios([["2023"]] + printed_run(2, 8))[0])

    def test_folios_agreeing_with_their_neighbours_are_read_as_printed(self) -> None:
        self.assertEqual([str(page + PRINTED_OFFSET) for page in range(1, 8)], self._folios(printed_run(1, 8)))

    def test_too_few_pages_elect_no_offset_and_carry_no_numbered_folio(self) -> None:
        self.assertEqual([None, None], self._folios([["2023"], ["384"]]))

    def test_a_second_run_of_pagination_keeps_its_own_folios(self) -> None:
        heads = printed_run(1, 8) + [[str(page - 7)] for page in range(8, 14)]
        self.assertEqual([str(page - 7) for page in range(8, 14)], self._folios(heads)[7:])

    def test_a_roman_folio_beside_a_numbered_run_is_kept(self) -> None:
        self.assertEqual("xi", self._folios([["xi"]] + printed_run(2, 8))[0])

    def test_a_page_with_no_furniture_takes_its_folio_from_the_pdfs_page_label(self) -> None:
        heads = [[f"Title {folio}"] for folio in (39, 40, 41)] + [[]]
        self.assertEqual("42", self._folios(heads, LabelledLayer())[3])


if __name__ == "__main__":
    unittest.main()
