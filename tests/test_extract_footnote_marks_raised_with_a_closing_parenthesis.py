from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, NOTE_OPENING, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, PageBlocks
from _extract.elements import Paragraph

MARK_WITH_A_PARENTHESIS = "1)"
RAISED_MARK = f"<sup>{MARK_WITH_A_PARENTHESIS}</sup>"


class TestFootnoteMarksRaisedWithAClosingParenthesis(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, MARK_WITH_A_PARENTHESIS, (f"1 {NOTE_OPENING}",))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, RAISED_MARK),
                                       notes_block(1, FOOTNOTE_KIND, f"<sup>1</sup> {NOTE_OPENING}")])]
        self.structure = self.built(pages, engine_pages)

    def test_the_mark_links_to_the_note_its_numeral_names(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual(f"{FIRST_SENTENCE}[^1]", paragraphs[0])

    def test_the_note_is_paired_with_its_mark(self) -> None:
        self.assertEqual([(1, NOTE_OPENING, True)],
                         [(definition.label, definition.text, definition.marked)
                          for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
