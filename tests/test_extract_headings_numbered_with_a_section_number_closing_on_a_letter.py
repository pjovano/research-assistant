from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.headings import section_number_of
from _extract.layer import TextLayer
from _extract.structure import Heading

FONT = "tiro"
HEADING_FONT = "tibo"
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 500.0
LINE_HALF_HEIGHT = 6.0
FILE_PAGE = 1
SUBLEVEL = 3
OPENING = "So much for what nature does for its own end with respect to the human race as a class."
CLOSING = "In the second part of his reflections the author turns to the question of what is essential."
OPENING_BASELINE = 80.0
TITLE_BASELINE = 120.0
CLOSING_BASELINE = 160.0
ROMAN_DOTTED_TITLE = "II.2.b. The prospective argument"
ARABIC_DOTTED_TITLE = "1.2.a. The retrospective argument"


class NumberedTitlePdf:
    def __init__(self, path: Path, title: str) -> None:
        self._path = path
        self._title = title

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for baseline, text, font in [(OPENING_BASELINE, OPENING, FONT), (TITLE_BASELINE, self._title, HEADING_FONT),
                                         (CLOSING_BASELINE, CLOSING, FONT)]:
                page.insert_text((LEFT, baseline), text, fontsize=BODY_SIZE, fontname=font)
            document.save(self._path)
        return self._path


def line_box(baseline: float) -> tuple:
    return (LEFT, baseline - BODY_SIZE - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


def engine_reading(title: str) -> list[Block]:
    return [BlockPlace(line_box(OPENING_BASELINE), 0).block(TEXT_KIND, f"<p>{OPENING}</p>"),
            BlockPlace(line_box(TITLE_BASELINE), 1).block(HEADING_KIND, f"<h4>{title}</h4>"),
            BlockPlace(line_box(CLOSING_BASELINE), 2).block(TEXT_KIND, f"<p>{CLOSING}</p>")]


class TestHeadingsNumberedWithASectionNumberClosingOnALetter(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _titles(self, title: str) -> list[str]:
        layer = TextLayer(NumberedTitlePdf(self._directory / "numbered.pdf", title).write())
        self.addCleanup(layer.close)
        page = PageBlocks(FILE_PAGE, engine_reading(title))
        result = page_assembler(layer, keep_everything()).assemble(page, [], SUBLEVEL)
        return [element.title for element in result.elements if isinstance(element, Heading)]

    def test_a_heading_numbered_in_roman_and_arabic_parts_closing_on_a_letter_stays_a_heading(self) -> None:
        self.assertEqual([ROMAN_DOTTED_TITLE], self._titles(ROMAN_DOTTED_TITLE))

    def test_a_heading_numbered_in_arabic_parts_closing_on_a_letter_stays_a_heading(self) -> None:
        self.assertEqual([ARABIC_DOTTED_TITLE], self._titles(ARABIC_DOTTED_TITLE))


class TestSectionNumbersClosingOnALetter(unittest.TestCase):
    def test_the_letter_is_the_last_part_of_the_number(self) -> None:
        self.assertEqual(("2", "2", "b"), section_number_of(ROMAN_DOTTED_TITLE))

    def test_a_roman_numeral_followed_by_a_letter_part_is_one_number(self) -> None:
        self.assertEqual(("2", "a"), section_number_of("II.a. The first objection"))

    def test_a_letter_opening_the_title_after_a_stop_and_a_space_is_no_part_of_the_number(self) -> None:
        self.assertEqual(("2",), section_number_of("2. A theory of number"))


if __name__ == "__main__":
    unittest.main()
