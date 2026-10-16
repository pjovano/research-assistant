from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.layer import LayerChar
from _extract.notationpages import NotationPagePlan, is_notation_page
from _layer_pdfs import RemappedPagesPdf, StandIn

MATH_FONT = "CMSY10"
PROSE_FONT = "Sabon"
ARROW_CODE = "~"
ARROW = StandIn("→")
PROSE_LINE = "The argument runs on in plain prose across the page."
NOTATION_LINE = "so p ~ q ~ r ~ s ~ t ~ u holds"


def chars(text: str, font: str) -> list[LayerChar]:
    return [LayerChar(char, (0.0, 0.0), False, 10.0, False, False, font) for char in text]


def is_math(font: str) -> bool:
    return font == MATH_FONT


class TestNotationPage(unittest.TestCase):
    def test_a_page_with_five_characters_in_a_math_font_carries_notation(self) -> None:
        self.assertTrue(is_notation_page(chars("Γ≻Δ⊢⊥", MATH_FONT) + chars("prose", PROSE_FONT), is_math))

    def test_a_page_with_five_operators_in_a_prose_font_carries_notation(self) -> None:
        self.assertTrue(is_notation_page(chars("p → q → r → s → t ⊢ u", PROSE_FONT), is_math))

    def test_a_page_of_prose_with_a_greek_quotation_carries_no_notation(self) -> None:
        self.assertFalse(is_notation_page(chars("Being is λόγος, as Heraclitus says.", PROSE_FONT), is_math))


class TestNotationPagesReadFromPixels(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def planned(self, pages: list[list[str]], chapters: list[tuple[str, int]]) -> list[int]:
        path = Path(self._directory.name) / "work.pdf"
        RemappedPagesPdf(path, pages, {ARROW_CODE: ARROW}, chapters).write()
        return NotationPagePlan(path).pages()

    def test_a_chapter_holding_one_notation_page_sends_only_that_page_to_the_engine(self) -> None:
        pages = [[PROSE_LINE], [PROSE_LINE, NOTATION_LINE], [PROSE_LINE], [PROSE_LINE]]
        self.assertEqual([2], self.planned(pages, [("One", 1), ("Two", 4)]))

    def test_a_work_with_no_notation_page_sends_nothing(self) -> None:
        self.assertEqual([], self.planned([[PROSE_LINE], [PROSE_LINE]], [("One", 1)]))


if __name__ == "__main__":
    unittest.main()
