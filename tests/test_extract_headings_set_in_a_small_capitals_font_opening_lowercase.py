from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading

DIVIDER = "chapter 2: ontology and the primacy of practice"
CLOSING_NOTE = "6. In addition to the article cited in note 2, above, see the later discussion."
OPENING_NOTE = "1. The early philosophy refers principally to the lectures of those years."
SUBLEVEL = 2
FILE_PAGE = 1
BODY_FONT = "helv"
HEADING_FONT = "tiro"
SMALL_CAPITALS_NAME = "/Bembo-SC"
ROMAN_NAME = "/Bembo-Roman"
BASE_FONT_KEY = "BaseFont"
LEFT = 72.0
RIGHT = 540.0
FONT_SIZE = 9.0
ROW_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 14.0


class NotesPage:
    def __init__(self, directory: Path, heading_font_name: str) -> None:
        self._path = directory / "notes.pdf"
        self._heading_font_name = heading_font_name
        self._rows = [(TEXT_KIND, CLOSING_NOTE), (HEADING_KIND, DIVIDER), (TEXT_KIND, OPENING_NOTE)]

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, (kind, text) in enumerate(self._rows):
                font = HEADING_FONT if kind == HEADING_KIND else BODY_FONT
                page.insert_text((LEFT, _baseline(index)), text, fontsize=FONT_SIZE, fontname=font)
            heading_font = next(font[0] for font in page.get_fonts() if font[4] == HEADING_FONT)
            document.xref_set_key(heading_font, BASE_FONT_KEY, self._heading_font_name)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, kind, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                                      for index, (kind, text) in enumerate(self._rows)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestHeadingsSetInASmallCapitalsFontOpeningLowercase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _texts(self, heading_font_name: str) -> list[str]:
        printed = NotesPage(self._directory, heading_font_name)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(printed.blocks, [], SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_lowercase_heading_in_a_small_capitals_font_opens_a_section(self) -> None:
        self.assertEqual([CLOSING_NOTE, DIVIDER, OPENING_NOTE], self._texts(SMALL_CAPITALS_NAME))

    def test_a_lowercase_heading_in_a_roman_font_reads_as_a_continuation_and_is_dropped(self) -> None:
        self.assertEqual([CLOSING_NOTE, OPENING_NOTE], self._texts(ROMAN_NAME))


if __name__ == "__main__":
    unittest.main()
