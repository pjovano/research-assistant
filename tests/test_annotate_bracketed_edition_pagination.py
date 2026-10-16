from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _book_fixtures import BookPage, BookPdf, BuiltPdfTestCase, ProseLines
from _annotate.cli import ReferenceLookup
import annotate

FURTHER_SIGLUM_PAGES = [BookPage(ProseLines(1).placing({30: "[C", 31: "12]", 90: "[A", 91: "12/C", 92: "13]"}))]
FURTHER_SIGLUM_PAGE = 1


class TestBracketedEditionPaginationUnderAnySiglum(unittest.TestCase):
    def setUp(self) -> None:
        self.grammar = annotate.MarkerGrammar()

    def test_a_further_siglum_is_read_as_edition_pagination(self) -> None:
        self.assertEqual([("C", 12, 0, "single")], self.grammar.scan("[C12]"))

    def test_a_siglum_of_several_capitals_is_read_as_edition_pagination(self) -> None:
        self.assertEqual([("GA", 41, 0, "single")], self.grammar.scan("[GA 41]"))

    def test_a_bracket_joining_a_further_siglum_yields_each_reference(self) -> None:
        found = self.grammar.scan("[A12/C13]")
        self.assertEqual([("A", 12, 0, "combined"), ("C", 13, 0, "combined")], found)

    def test_a_bracket_joining_three_references_yields_each_reference(self) -> None:
        found = self.grammar.scan("[A1/B2/C3]")
        self.assertEqual(["A", "B", "C"], [edition for edition, _, _, _ in found])

    def test_a_bracket_joining_a_siglum_and_a_volume_yields_both(self) -> None:
        found = self.grammar.scan("[A12/4:255]")
        self.assertEqual([("A", 12, 0, "combined"), ("Ak4", 255, 0, "combined")], found)


class TestBracketsThatAreNotEditionPagination(unittest.TestCase):
    def setUp(self) -> None:
        self.grammar = annotate.MarkerGrammar()

    def test_a_citation_number_is_not_edition_pagination(self) -> None:
        self.assertEqual([], self.grammar.scan("as argued elsewhere [12], the claim"))

    def test_a_bracketed_year_is_not_edition_pagination(self) -> None:
        self.assertEqual([], self.grammar.scan("first published [2000] in German"))

    def test_bracketed_prose_is_not_edition_pagination(self) -> None:
        for text in ("[sic]", "[emphasis added]", "[The author adds 12]", "[SO]", "[A12 and more]"):
            with self.subTest(text=text):
                self.assertEqual([], self.grammar.scan(text))


class TestAFurtherSiglumAnchorsInAPdf(BuiltPdfTestCase):
    BOOK = BookPdf(FURTHER_SIGLUM_PAGES)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.index = annotate.EditionAnchorIndex(cls.pdf)

    def test_a_further_siglum_makes_the_inline_marker_strategy_available(self) -> None:
        self.assertIn("inline-marker", self.index.strategies())

    def test_a_further_siglum_resolves_to_the_page_that_prints_it(self) -> None:
        self.assertEqual([FURTHER_SIGLUM_PAGE], [marker.page for marker in self.index.inline.resolve("C", 12)])

    def test_a_further_siglum_in_a_joined_bracket_resolves(self) -> None:
        self.assertTrue(self.index.inline.resolve("C", 13))

    def test_locate_resolves_a_reference_under_a_further_siglum(self) -> None:
        self.assertIn("C12 -> p1", ReferenceLookup(self.pdf).rendered("C12"))


class TestAMarkerTailUnderAFurtherSiglumIsDebris(unittest.TestCase):
    def test_a_trailing_opener_under_a_further_siglum_is_stripped(self) -> None:
        self.assertEqual("composed.", annotate.MarkerTail.stripped("composed.[C"))

    def test_a_middle_piece_under_a_further_siglum_is_debris(self) -> None:
        self.assertTrue(annotate.MarkerTail.is_pure_debris("12/C"))

    def test_a_word_opening_bracketed_prose_is_not_stripped(self) -> None:
        self.assertEqual("composed.[The", annotate.MarkerTail.stripped("composed.[The"))


if __name__ == "__main__":
    unittest.main()
