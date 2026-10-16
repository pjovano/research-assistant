from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, SECOND_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, PageBlocks
from _extract.elements import Paragraph

CARRIED_NOTE = "SW I, p. 91; Science of Knowledge, p. 93."
OWN_NOTE = "SW I, p. 48; EPW, p. 108."


class TestFootnotesPrintedOnThePageAfterTheirMark(FooterCase):
    def setUp(self) -> None:
        notes = (f"1 {CARRIED_NOTE}", f"2 {OWN_NOTE}")
        pages = [NotedPage(FIRST_SENTENCE, "1", ()), NotedPage(SECOND_SENTENCE, "2", notes)]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>1</sup>")]),
                        PageBlocks(2, [body_block(2, SECOND_SENTENCE, "<sup>2</sup>"),
                                       notes_block(2, FOOTNOTE_KIND, " ".join(notes))])]
        self.structure = self.built(pages, engine_pages)

    def test_the_note_printed_on_the_next_page_takes_its_numeral_ahead_of_that_pages_own_notes(self) -> None:
        self.assertEqual([(1, CARRIED_NOTE), (2, OWN_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])

    def test_the_mark_on_the_page_before_links_to_the_carried_note(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual(f"{FIRST_SENTENCE}[^1]", paragraphs[0])

    def test_neither_the_mark_nor_the_carried_note_is_logged_unpaired(self) -> None:
        self.assertEqual([], self.structure.footnote_log())


if __name__ == "__main__":
    unittest.main()
