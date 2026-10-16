from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, SECOND_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, PageBlocks
from _extract.elements import Paragraph

SUPERSCRIPT_TWO = "²"
NOTE = "Specifically, these investigations are carried out by unifying the pure part."
CONTINUATION = "and so the pure part grounds the empirical."


class TestFootnoteMarksSetAsSuperscriptDigits(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, SUPERSCRIPT_TWO, (f"2 {NOTE}",)),
                 NotedPage(SECOND_SENTENCE, "", (CONTINUATION,))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, SUPERSCRIPT_TWO),
                                       notes_block(1, FOOTNOTE_KIND, f"2 {NOTE}")]),
                        PageBlocks(2, [body_block(2, SECOND_SENTENCE, ""),
                                       notes_block(2, FOOTNOTE_KIND, CONTINUATION)])]
        self.structure = self.built(pages, engine_pages)

    def test_the_superscript_digit_links_to_the_note_the_page_prints_under_its_numeral(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual(f"{FIRST_SENTENCE}[^2]", paragraphs[0])

    def test_the_note_keeps_its_numeral_and_takes_its_continuation_from_the_next_page(self) -> None:
        self.assertEqual([(2, f"{NOTE} {CONTINUATION}")],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
