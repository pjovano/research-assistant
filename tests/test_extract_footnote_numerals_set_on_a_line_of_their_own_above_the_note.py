from __future__ import annotations

import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_NOTE_BASELINE, FIRST_SENTENCE, FONT, LEFT, MARK_SIZE, NOTE_SIZE, SECOND_NOTE_BASELINE, EngineRegion,
    FooterCase, NotedPage, body_block,
)
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, PageBlocks
from _extract.elements import Paragraph

NUMERAL = "5"
NOTE = "Before Kant, semantic theory assumed that its explanations had to start out from concepts."


@dataclass(frozen=True)
class NumeralAboveItsNotePage:
    sentence: str

    def draw_on(self, page) -> None:
        NotedPage(self.sentence, NUMERAL, ()).draw_on(page)
        page.insert_text((LEFT, FIRST_NOTE_BASELINE), NUMERAL, fontsize=MARK_SIZE, fontname=FONT)
        page.insert_text((LEFT, SECOND_NOTE_BASELINE), NOTE, fontsize=NOTE_SIZE, fontname=FONT)


class TestFootnoteNumeralsSetOnALineOfTheirOwnAboveTheNote(FooterCase):
    def setUp(self) -> None:
        engine_page = PageBlocks(1, [
            body_block(1, FIRST_SENTENCE, f"<sup>{NUMERAL}</sup>"),
            EngineRegion(FIRST_NOTE_BASELINE, FIRST_NOTE_BASELINE).block(1, TEXT_KIND, f"<p>{NUMERAL}</p>"),
            EngineRegion(SECOND_NOTE_BASELINE, SECOND_NOTE_BASELINE).block(1, FOOTNOTE_KIND, f"<p>{NOTE}</p>"),
        ])
        self.structure = self.built([NumeralAboveItsNotePage(FIRST_SENTENCE)], [engine_page])

    def test_the_note_opens_on_the_numeral_set_above_it(self) -> None:
        self.assertEqual([(int(NUMERAL), NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])

    def test_the_numeral_leaves_the_body(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual([f"{FIRST_SENTENCE}[^{NUMERAL}]"], paragraphs)


if __name__ == "__main__":
    unittest.main()
