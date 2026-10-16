from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, SECOND_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTER_KIND, PageBlocks

FIRST_CITATION = "GA, II 3, 189."
SECOND_CITATION = "GA, II 3, 192."
PRINTED_NOTES = ((1, FIRST_SENTENCE, FIRST_CITATION), (2, SECOND_SENTENCE, SECOND_CITATION))


class TestFooterNotesWhoseWordsApartFromTheirNumeralsRepeatOnAnotherPage(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(sentence, str(page), (f"{page} {citation}",)) for page, sentence, citation in PRINTED_NOTES]
        engine_pages = [PageBlocks(page, [body_block(page, sentence, str(page)),
                                          notes_block(page, FOOTER_KIND, f"{page} {citation}")])
                        for page, sentence, citation in PRINTED_NOTES]
        self.structure = self.built(pages, engine_pages)

    def test_each_footer_note_pairs_with_its_mark(self) -> None:
        self.assertEqual([FIRST_CITATION, SECOND_CITATION],
                         [definition.text for definition in self.structure.definitions()])

    def test_no_mark_is_left_without_its_note(self) -> None:
        self.assertEqual([], self.structure.footnote_log())


if __name__ == "__main__":
    unittest.main()
