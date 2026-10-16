from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, SECOND_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, PageBlocks
from _extract.elements import Paragraph

SUPERSCRIPT_THREE = "³"
FIRST_NOTE = "The list is not exhaustive, and other uses merit attention."
SECOND_NOTE = "For an overview of the surveyability of proofs, see the survey."


class TestFootnotesOpeningOnANumeralSetAsSuperscriptDigits(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "2", (f"2 {FIRST_NOTE}",)),
                 NotedPage(SECOND_SENTENCE, SUPERSCRIPT_THREE, (f"{SUPERSCRIPT_THREE} {SECOND_NOTE}",))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>2</sup>"),
                                       notes_block(1, FOOTNOTE_KIND, f"2 {FIRST_NOTE}")]),
                        PageBlocks(2, [body_block(2, SECOND_SENTENCE, SUPERSCRIPT_THREE),
                                       notes_block(2, FOOTNOTE_KIND, f"{SUPERSCRIPT_THREE} {SECOND_NOTE}")])]
        self.structure = self.built(pages, engine_pages)

    def test_the_superscript_digit_in_the_body_links_to_the_note_opening_on_it(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual(f"{SECOND_SENTENCE}[^3]", paragraphs[1])

    def test_the_note_opening_on_superscript_digits_stands_apart_from_the_note_before(self) -> None:
        self.assertEqual([(2, FIRST_NOTE), (3, SECOND_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])

    def test_no_mark_is_left_without_its_note(self) -> None:
        self.assertEqual([], self.structure.footnote_log())


if __name__ == "__main__":
    unittest.main()
