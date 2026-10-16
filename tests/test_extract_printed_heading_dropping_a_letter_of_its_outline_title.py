from __future__ import annotations

import unittest
from dataclasses import dataclass

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeLayer, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.headings import HeadingMatch
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

OUTLINE_TITLE = "2 On the Independence of Moral Reasons"
PRINTED_TITLE = "2 On the Independnce of Moral Reasons"
CLOSING_PROSE = "So the question of the section before remains open at its close."
OPENING_PROSE = "The next section asks whether reasons of this kind hold of themselves."


@dataclass(frozen=True)
class Band:
    top: float
    bottom: float
    index: int


def block(kind: str, text: str, band: Band) -> Block:
    box = (50.0, band.top, 390.0, band.bottom)
    return Block(1, kind, f"<p>{text}</p>", box, {}, f"/page/1/{kind}/{band.index}")


class TestAPrintedHeadingDroppingALetterOfItsOutlineTitle(unittest.TestCase):
    def test_a_heading_dropping_a_letter_inside_a_long_word_matches_its_outline_title(self) -> None:
        self.assertTrue(HeadingMatch().matches(PRINTED_TITLE, OUTLINE_TITLE))

    def test_a_heading_dropping_a_letter_inside_a_six_letter_word_matches(self) -> None:
        self.assertTrue(HeadingMatch().matches("Tropes of Sense", "Trpes of Sense"))

    def test_a_heading_dropping_a_letter_inside_a_five_letter_word_does_not_match(self) -> None:
        self.assertFalse(HeadingMatch().matches("Being and Time", "Bing and Time"))

    def test_a_heading_dropping_a_word_s_last_letter_does_not_match(self) -> None:
        self.assertFalse(HeadingMatch().matches("The Concepts of Nature", "The Concept of Nature"))

    def test_a_heading_dropping_a_letter_in_two_words_does_not_match(self) -> None:
        self.assertFalse(HeadingMatch().matches("On the Independnce of Moral Reasns",
                                                "On the Independence of Moral Reasons"))

    def test_the_outline_entry_opens_once_where_the_page_prints_its_heading(self) -> None:
        blocks = [block(TEXT_KIND, CLOSING_PROSE, Band(90.0, 360.0, 0)),
                  block(HEADING_KIND, PRINTED_TITLE, Band(395.0, 410.0, 1)),
                  block(TEXT_KIND, OPENING_PROSE, Band(424.0, 510.0, 2))]
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), [OutlineHeading(1, OUTLINE_TITLE, 1)], None).elements[1:]
        texts = [element.title if isinstance(element, Heading) else element.text for element in elements]
        self.assertEqual([CLOSING_PROSE, OUTLINE_TITLE, OPENING_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
