from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, SECOND_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, PageBlocks

OPENING = "In my earlier paper, I focused on genealogy"
NOTE = f"{OPENING} more generally."


class TestFootnoteOpeningsPrintedAgainInFullOnThePageOfTheirMark(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "", (f"2 {OPENING}",)), NotedPage(SECOND_SENTENCE, "2", (f"2 {NOTE}",))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, ""),
                                       notes_block(1, FOOTNOTE_KIND, f"2 {OPENING}")]),
                        PageBlocks(2, [body_block(2, SECOND_SENTENCE, "<sup>2</sup>"),
                                       notes_block(2, FOOTNOTE_KIND, f"2 {NOTE}")])]
        self.structure = self.built(pages, engine_pages)

    def test_the_note_is_defined_once_in_full(self) -> None:
        self.assertEqual([(2, NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
