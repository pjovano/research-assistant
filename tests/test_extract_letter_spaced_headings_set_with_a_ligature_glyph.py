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
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

OUTLINE_TITLE = "Final Causes"
PRINTED_TITLE = "ﬁnal causes"
TITLE_IN_LETTERS = "final causes"
CARRIED_PROSE = "and so the argument carried over from the page before comes to its end."
OPENING_PROSE = "The section opens with this sentence about the ends of natural things."
SECTION_LEVEL = 1
SUBLEVEL = 2
BUILTIN_FONT = "tiro"
EMBEDDED_FONT = "F0"
LEFT = 72.0
RIGHT = 540.0
HEADING_SIZE = 11.0
BODY_SIZE = 10.0
LETTER_SPACING_SHARE = 0.25
WORD_SPACING_SHARE = 1.0
ROW_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 16.0


class LetterSpacedPage:
    def __init__(self, directory: Path, rows: list[tuple[str, str]]) -> None:
        self._path = directory / "sections.pdf"
        self._rows = rows

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_font(fontname=EMBEDDED_FONT, fontbuffer=pymupdf.Font(BUILTIN_FONT).buffer)
            for index, (kind, text) in enumerate(self._rows):
                if kind == HEADING_KIND:
                    self._write_spaced(page, text, _baseline(index))
                else:
                    page.insert_text((LEFT, _baseline(index)), text, fontsize=BODY_SIZE, fontname=EMBEDDED_FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _write_spaced(page, text: str, baseline: float) -> None:
        font, left = pymupdf.Font(BUILTIN_FONT), LEFT
        for char in text:
            if char == " ":
                left += WORD_SPACING_SHARE * HEADING_SIZE
                continue
            page.insert_text((left, baseline), char, fontsize=HEADING_SIZE, fontname=EMBEDDED_FONT)
            left += font.text_length(char, fontsize=HEADING_SIZE) + LETTER_SPACING_SHARE * HEADING_SIZE

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(1, [Block(1, kind, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                              for index, (kind, text) in enumerate(self._rows)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestLetterSpacedHeadingsSetWithALigatureGlyph(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _texts(self, due: list[OutlineHeading]) -> list[str]:
        printed = LetterSpacedPage(self._directory, [(TEXT_KIND, CARRIED_PROSE), (HEADING_KIND, PRINTED_TITLE),
                                                      (TEXT_KIND, OPENING_PROSE)])
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(printed.blocks, due, SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_the_outline_entry_of_the_heading_opens_where_the_heading_prints_once(self) -> None:
        texts = self._texts([OutlineHeading(SECTION_LEVEL, OUTLINE_TITLE, 1)])
        self.assertEqual([CARRIED_PROSE, OUTLINE_TITLE, OPENING_PROSE], texts)

    def test_the_heading_without_an_outline_entry_writes_the_ligature_as_its_letters(self) -> None:
        self.assertEqual([CARRIED_PROSE, TITLE_IN_LETTERS, OPENING_PROSE], self._texts([]))


if __name__ == "__main__":
    unittest.main()
