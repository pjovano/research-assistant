from __future__ import annotations

import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    BODY_SIZE, FIRST_SENTENCE, FONT, LEFT, LINE_HALF_HEIGHT, RIGHT, FooterCase, NotedPage, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.elements import Paragraph

HEADING = "Indefinites and Arbitrary Reference"
HEADING_BASELINE = 70.0
NOTE = "Psillos, for instance, states as much."


@dataclass(frozen=True)
class HeadedPage:
    def draw_on(self, page) -> None:
        page.insert_text((LEFT, HEADING_BASELINE), HEADING, fontsize=BODY_SIZE, fontname=FONT)
        NotedPage(FIRST_SENTENCE, "1", (f"1 {NOTE}",)).draw_on(page)


def heading_block() -> Block:
    box = (LEFT, HEADING_BASELINE - LINE_HALF_HEIGHT, RIGHT, HEADING_BASELINE + LINE_HALF_HEIGHT / 2)
    return Block(1, HEADING_KIND, f"<h2>{HEADING}</h2>", box, {}, "/page/1/SectionHeader/0")


def body_block() -> Block:
    box = (LEFT, 92.0, RIGHT, 104.0)
    return Block(1, TEXT_KIND, f"<p>{FIRST_SENTENCE}<sup>1</sup></p>", box, {}, "/page/1/Text/1")


class TestSectionHeadingsNamingAReferenceInTheSingular(FooterCase):
    def setUp(self) -> None:
        engine_page = PageBlocks(1, [heading_block(), body_block(), notes_block(1, FOOTNOTE_KIND, f"1 {NOTE}")])
        self.structure = self.built([HeadedPage()], [engine_page])

    def test_the_section_reads_as_prose_whose_mark_links_to_its_note(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual([f"{FIRST_SENTENCE}[^1]"], paragraphs)


if __name__ == "__main__":
    unittest.main()
