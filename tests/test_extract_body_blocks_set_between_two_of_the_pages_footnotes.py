from __future__ import annotations

import unittest
from dataclasses import dataclass

import pymupdf

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    BODY_BASELINE, BODY_SIZE, FIRST_SENTENCE, FONT, LEFT, MARK_RISE, MARK_SIZE, NOTE_SIZE, SECOND_SENTENCE,
    EngineRegion, FooterCase, NotedPage,
)
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, PageBlocks
from _extract.elements import Paragraph

SECOND_BODY_BASELINE = BODY_BASELINE + 12.0
NOTE_BASELINE = 540.0
LIST_BASELINE = 556.0
NEXT_NOTE_BASELINE = 572.0
NOTE = "The following editions have been used:"
EDITION = "WL: Wissenschaft der Logik, vol. I,"
ORDINAL_SUFFIX = "nd ed."
NEXT_NOTE = "See, for example, the first edition."


@dataclass(frozen=True)
class RaisedText:
    baseline: float
    text: str
    raised: str
    after: str = ""

    def draw_on(self, page, size: float) -> None:
        page.insert_text((LEFT, self.baseline), self.text, fontsize=size, fontname=FONT)
        raised_left = LEFT + pymupdf.get_text_length(self.text, FONT, size)
        page.insert_text((raised_left, self.baseline - MARK_RISE), self.raised, fontsize=MARK_SIZE, fontname=FONT)
        after_left = raised_left + pymupdf.get_text_length(self.raised, FONT, MARK_SIZE)
        page.insert_text((after_left, self.baseline), self.after, fontsize=size, fontname=FONT)


@dataclass(frozen=True)
class ListInsideANotePage:
    def draw_on(self, page) -> None:
        NotedPage(FIRST_SENTENCE, "1", ()).draw_on(page)
        RaisedText(SECOND_BODY_BASELINE, SECOND_SENTENCE, "2").draw_on(page, BODY_SIZE)
        page.insert_text((LEFT, NOTE_BASELINE), f"1 {NOTE}", fontsize=NOTE_SIZE, fontname=FONT)
        RaisedText(LIST_BASELINE, f"{EDITION} ", "2", ORDINAL_SUFFIX).draw_on(page, NOTE_SIZE)
        page.insert_text((LEFT, NEXT_NOTE_BASELINE), f"2 {NEXT_NOTE}", fontsize=NOTE_SIZE, fontname=FONT)


class TestBodyBlocksSetBetweenTwoOfThePagesFootnotes(FooterCase):
    def setUp(self) -> None:
        engine_page = PageBlocks(1, [
            EngineRegion(BODY_BASELINE, SECOND_BODY_BASELINE).block(
                1, TEXT_KIND, f"<p>{FIRST_SENTENCE}<sup>1</sup> {SECOND_SENTENCE}<sup>2</sup></p>"),
            EngineRegion(NOTE_BASELINE, NOTE_BASELINE).block(1, FOOTNOTE_KIND, f"<p>1 {NOTE}</p>"),
            EngineRegion(LIST_BASELINE, LIST_BASELINE).block(1, TEXT_KIND,
                                                              f"<p>{EDITION} <sup>2</sup>{ORDINAL_SUFFIX}</p>"),
            EngineRegion(NEXT_NOTE_BASELINE, NEXT_NOTE_BASELINE).block(1, FOOTNOTE_KIND, f"<p>2 {NEXT_NOTE}</p>"),
        ])
        self.structure = self.built([ListInsideANotePage()], [engine_page])

    def test_the_block_continues_the_note_above_it(self) -> None:
        self.assertEqual([(1, f"{NOTE} {EDITION} <sup>2</sup>{ORDINAL_SUFFIX}"), (2, NEXT_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])

    def test_the_block_leaves_the_body(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual([f"{FIRST_SENTENCE}[^1] {SECOND_SENTENCE}[^2]"], paragraphs)


if __name__ == "__main__":
    unittest.main()
