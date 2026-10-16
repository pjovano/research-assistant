from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _writing.notation_restoration import NotationRestoration
from _writing.quotations import PdfQuotation, QuotationRequest

SOURCE = "Hegel - 2010 - The Science of Logic"
PROSE_PAGE = "Kant has declared the proposition 5 7 12 to be synthetic"
QUOTED = "Kant has declared the proposition 5 + 7 = 12 to be synthetic"


class StubVerification:
    def __init__(self, page_text: str, notation: list[str]) -> None:
        self._payload = {"verified": True, "ambiguous": False, "notation_read_from_page": notation,
                         "hits": [{"pdf_page": 776, "printed_page": "703", "page_text": page_text, "link": None}]}

    def payload(self, request: QuotationRequest) -> dict:
        return self._payload


class TestMathFontNotationKeptInTheReference(unittest.TestCase):
    def test_standalone_operators_set_in_a_math_font_stand_where_the_quotation_sets_them(self) -> None:
        self.assertEqual(QUOTED, NotationRestoration(QUOTED, PROSE_PAGE, ("+", "=")).restored())

    def test_a_math_font_letter_standing_alone_is_kept(self) -> None:
        restored = NotationRestoration("from ‘λ is P’ it follows", "from ‘ is P’ it follows", ("λ",)).restored()
        self.assertEqual("from ‘λ is P’ it follows", restored)

    def test_notation_glued_to_a_word_is_kept_with_it(self) -> None:
        restored = NotationRestoration("the sum x+y holds", "the sum xy holds", ("+",)).restored()
        self.assertEqual("the sum x+y holds", restored)

    def test_the_pages_spelling_of_the_prose_wins(self) -> None:
        restored = NotationRestoration("the ﬁrst sum 5 + 7", "the first sum 5 7", ("+",)).restored()
        self.assertEqual("the first sum 5 + 7", restored)

    def test_a_delimited_span_stands_where_the_quotation_sets_it(self) -> None:
        restored = NotationRestoration("so that $a + b$ is the sum", "so that is the sum", ("$a + b$",)).restored()
        self.assertEqual("so that $a + b$ is the sum", restored)

    def test_notation_closing_the_quotation_is_kept(self) -> None:
        self.assertEqual("the sum is 12 =", NotationRestoration("the sum is 12 =", "the sum is 12", ("=",)).restored())

    def test_a_quotation_without_notation_takes_the_page_text_as_it_stands(self) -> None:
        self.assertEqual("words  of the\npage", NotationRestoration("words of the page", "words  of the\npage", ()).restored())

    def test_the_reference_carries_the_notation_and_names_it_to_read_on_the_page(self) -> None:
        quotation = PdfQuotation(StubVerification(PROSE_PAGE, ["+", "="])).verified(QuotationRequest(SOURCE, QUOTED))
        self.assertEqual((QUOTED, ("+", "=")), (quotation.wording, quotation.notation_to_read))


if __name__ == "__main__":
    unittest.main()
