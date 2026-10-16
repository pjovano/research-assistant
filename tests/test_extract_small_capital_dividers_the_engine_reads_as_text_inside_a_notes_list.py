from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.policy import SectionOpening
from _extract.structure import Heading

NOTES_TITLE = "Notes"
CLOSING_NOTE = "21. Zur Sache des Denkens, p. 76."
DIVIDER = "chapter 6: the descent of the logos"
OPENING_NOTE = "1. Thomas Aquinas, Questiones disputatae de veritate, qu. 1, art. 1."
NOTES_LEVEL = 1
SUBLEVEL = 2
FILE_PAGE = 1
BODY_FONT = "helv"
DIVIDER_FONT = "tiro"
SMALL_CAPITALS_NAME = "/Bembo-SC"
ROMAN_NAME = "/Bembo-Roman"
BASE_FONT_KEY = "BaseFont"
LEFT = 72.0
RIGHT = 540.0
FONT_SIZE = 9.0
ROW_PITCH = 20.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 11.0


class NotesListPage:
    def __init__(self, directory: Path, divider_font_name: str) -> None:
        self._path = directory / "notes.pdf"
        self._divider_font_name = divider_font_name
        self._rows = [CLOSING_NOTE, DIVIDER, OPENING_NOTE]

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, text in enumerate(self._rows):
                font = DIVIDER_FONT if text == DIVIDER else BODY_FONT
                page.insert_text((LEFT, _baseline(index)), text, fontsize=FONT_SIZE, fontname=font)
            divider_font = next(font[0] for font in page.get_fonts() if font[4] == DIVIDER_FONT)
            document.xref_set_key(divider_font, BASE_FONT_KEY, self._divider_font_name)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, TEXT_KIND, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                                      for index, text in enumerate(self._rows)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 3.0)


class TestSmallCapitalDividersTheEngineReadsAsTextInsideANotesList(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _elements(self, divider_font_name: str) -> list:
        printed = NotesListPage(self._directory, divider_font_name)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        policy = keep_everything()
        policy.opens(SectionOpening(NOTES_LEVEL, NOTES_TITLE))
        assembler = page_assembler(layer, policy)
        return assembler.assemble(printed.blocks, [], SUBLEVEL).elements[1:]

    def _written(self, divider_font_name: str) -> list[tuple[str, str]]:
        return [(type(element).__name__, getattr(element, "title", None) or element.text)
                for element in self._elements(divider_font_name)]

    def test_an_unnumbered_line_in_small_capitals_opens_a_section_between_the_notes(self) -> None:
        self.assertEqual([("Paragraph", CLOSING_NOTE), ("Heading", DIVIDER), ("Paragraph", OPENING_NOTE)],
                         self._written(SMALL_CAPITALS_NAME))

    def test_an_unnumbered_line_in_roman_type_stays_text_of_the_notes(self) -> None:
        self.assertNotIn(("Heading", DIVIDER), self._written(ROMAN_NAME))

    def test_the_divider_is_written_at_the_sections_sublevel(self) -> None:
        levels = [element.level for element in self._elements(SMALL_CAPITALS_NAME) if isinstance(element, Heading)]
        self.assertEqual([SUBLEVEL], levels)


if __name__ == "__main__":
    unittest.main()
