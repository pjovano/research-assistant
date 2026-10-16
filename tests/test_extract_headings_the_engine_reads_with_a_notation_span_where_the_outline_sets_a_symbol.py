from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

OUTLINE_TITLE = "4.2 ⊗-Categories and Tensor Products"
ENGINE_HEADING = "<h3>4.2 <math>\\otimes</math>-Categories and Tensor Products</h3>"
CARRIED_PROSE = "and so the proof carried over from the page before comes to its end."
OPENING_PROSE = "We now pass to a structure in which the comma of a sequent becomes a connective."
SECTION_LEVEL = 1
SUBLEVEL = 2
FILE_PAGE = 1
BUILTIN_FONT = "tiro"
EMBEDDED_FONT = "F0"
LEFT = 72.0
RIGHT = 540.0
FONT_SIZE = 11.0
ROW_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 16.0


class PixelReadPage:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "section.pdf"
        self._rows = [(TEXT_KIND, CARRIED_PROSE, f"<p>{CARRIED_PROSE}</p>"),
                      (HEADING_KIND, OUTLINE_TITLE, ENGINE_HEADING),
                      (TEXT_KIND, OPENING_PROSE, f"<p>{OPENING_PROSE}</p>")]

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_font(fontname=EMBEDDED_FONT, fontbuffer=pymupdf.Font(BUILTIN_FONT).buffer)
            for index, (_kind, printed, _html) in enumerate(self._rows):
                page.insert_text((LEFT, _baseline(index)), printed, fontsize=FONT_SIZE, fontname=EMBEDDED_FONT)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, kind, html, _box(index), {}, f"/page/1/{index}")
                                      for index, (kind, _printed, html) in enumerate(self._rows)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestHeadingsTheEngineReadsWithANotationSpanWhereTheOutlineSetsASymbol(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def test_the_outline_entry_opens_where_the_heading_prints_once(self) -> None:
        printed = PixelReadPage(self._directory)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        due = [OutlineHeading(SECTION_LEVEL, OUTLINE_TITLE, FILE_PAGE)]
        elements = assembler.assemble(printed.blocks, due, SUBLEVEL).elements[1:]
        texts = [element.title if isinstance(element, Heading) else element.text for element in elements]
        self.assertEqual([CARRIED_PROSE, OUTLINE_TITLE, OPENING_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
