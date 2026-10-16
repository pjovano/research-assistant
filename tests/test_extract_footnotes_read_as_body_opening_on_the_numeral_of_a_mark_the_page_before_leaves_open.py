from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, SECOND_SENTENCE, FooterCase, NotedPage, body_block, notes_block,
)
from _extract.blocks import TEXT_KIND, PageBlocks
from _extract.elements import Paragraph

CARRIED_NOTE = "Thus, for example, the second theorem follows."
PAGES_OWN_NOTE = "See the first edition."


class TestFootnotesReadAsBodyOpeningOnTheNumeralOfAMarkThePageBeforeLeavesOpen(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "40", ()),
                 NotedPage(SECOND_SENTENCE, "41", (f"40 {CARRIED_NOTE}", f"41 {PAGES_OWN_NOTE}"))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>40</sup>")]),
                        PageBlocks(2, [body_block(2, SECOND_SENTENCE, "<sup>41</sup>"),
                                       notes_block(2, TEXT_KIND, f"40 {CARRIED_NOTE} 41 {PAGES_OWN_NOTE}")])]
        self.structure = self.built(pages, engine_pages)

    def test_the_block_defines_the_open_mark_and_the_pages_own_mark(self) -> None:
        self.assertEqual([(40, CARRIED_NOTE), (41, PAGES_OWN_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])

    def test_the_block_leaves_the_body(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual([f"{FIRST_SENTENCE}[^40]", f"{SECOND_SENTENCE}[^41]"], paragraphs)


if __name__ == "__main__":
    unittest.main()
