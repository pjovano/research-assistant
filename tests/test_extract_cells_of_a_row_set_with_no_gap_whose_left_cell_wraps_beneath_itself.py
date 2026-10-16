from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
FONT_SIZE = 10.0
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 14.0
BLOCK_RIGHT = 400.0
LEFT_CELL = ("(d) every not-man does not", "recover")
RIGHT_CELL = "(c) every not-man recovers"
SHORT_RUN = "M,"


def _paragraph_of(path: Path, opening: str, abutting: str) -> str:
    _write_cells(path, opening, abutting)
    layer = TextLayer(path)
    try:
        box = (LEFT, FIRST_BASELINE - LINE_PITCH, BLOCK_RIGHT, FIRST_BASELINE + LINE_PITCH)
        block = Block(1, TEXT_KIND, "", box, {}, "/page/1/Text/0")
        inputs = StructureInputs(DocumentBlocks([PageBlocks(1, [block])]), [], WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        paragraph, = [element.text for element in elements if isinstance(element, Paragraph)]
        return paragraph
    finally:
        layer.close()


def _write_cells(path: Path, opening: str, abutting: str) -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((LEFT, FIRST_BASELINE), opening, fontsize=FONT_SIZE, fontname=FONT)
        page.insert_text((LEFT, FIRST_BASELINE + LINE_PITCH), LEFT_CELL[1], fontsize=FONT_SIZE, fontname=FONT)
        abutting_left = LEFT + pymupdf.get_text_length(opening, FONT, FONT_SIZE)
        page.insert_text((abutting_left, FIRST_BASELINE), abutting, fontsize=FONT_SIZE, fontname=FONT)
        document.save(path)


class TestCellsOfARowSetWithNoGapWhoseLeftCellWrapsBeneathItself(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "cells.pdf"

    def test_the_left_cell_reads_whole_before_the_right_cell(self) -> None:
        paragraph = _paragraph_of(self._path, LEFT_CELL[0], RIGHT_CELL)
        self.assertEqual(f"{' '.join(LEFT_CELL)} {RIGHT_CELL}", paragraph)

    def test_a_run_too_short_to_be_a_cell_stays_on_its_line(self) -> None:
        paragraph = _paragraph_of(self._path, LEFT_CELL[0], SHORT_RUN)
        self.assertEqual(f"{LEFT_CELL[0]}{SHORT_RUN} {LEFT_CELL[1]}", paragraph)


if __name__ == "__main__":
    unittest.main()
