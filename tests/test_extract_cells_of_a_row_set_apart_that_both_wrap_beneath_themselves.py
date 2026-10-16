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
FONT_SIZE = 9.0
LEFT = 72.0
RIGHT_CELL_LEFT = 260.0
FIRST_BASELINE = 100.0
LINE_PITCH = 11.0
BLOCK_RIGHT = 480.0
LEFT_CELL = ("(2) It would not be possible that p if", "we did not think that q.")
RIGHT_CELL = ("I cannot perceive an object without", "conceiving it as distinct from myself.")
LABELS = ("1.", "2.")
LABELLED_TEXTS = ("The first objection is the bearing objection.", "The second objection is the logical one.")
LABEL_TEXT_LEFT = 86.0


def _paragraph_of(path: Path, placed_lines: list[tuple[float, int, str]]) -> str:
    _write_lines(path, placed_lines)
    layer = TextLayer(path)
    try:
        box = (LEFT, FIRST_BASELINE - LINE_PITCH, BLOCK_RIGHT, FIRST_BASELINE + LINE_PITCH)
        block = Block(1, TEXT_KIND, "", box, {}, "/page/1/Text/0")
        inputs = StructureInputs(DocumentBlocks([PageBlocks(1, [block])]), [], WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return " ".join(element.text for element in elements if isinstance(element, Paragraph))
    finally:
        layer.close()


def _write_lines(path: Path, placed_lines: list[tuple[float, int, str]]) -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        for left, row, text in placed_lines:
            page.insert_text((left, FIRST_BASELINE + row * LINE_PITCH), text, fontsize=FONT_SIZE, fontname=FONT)
        document.save(path)


def _cells_of_one_row() -> list[tuple[float, int, str]]:
    return [(LEFT, row, text) for row, text in enumerate(LEFT_CELL)] \
        + [(RIGHT_CELL_LEFT, row, text) for row, text in enumerate(RIGHT_CELL)]


def _labelled_lines() -> list[tuple[float, int, str]]:
    return [(LEFT, row, label) for row, label in enumerate(LABELS)] \
        + [(LABEL_TEXT_LEFT, row, text) for row, text in enumerate(LABELLED_TEXTS)]


class TestCellsOfARowSetApartThatBothWrapBeneathThemselves(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "cells.pdf"

    def test_the_left_cell_reads_whole_before_the_right_cell(self) -> None:
        paragraph = _paragraph_of(self._path, _cells_of_one_row())
        self.assertEqual(f"{' '.join(LEFT_CELL)} {' '.join(RIGHT_CELL)}", paragraph)

    def test_labels_set_apart_from_their_lines_stay_on_their_lines(self) -> None:
        paragraph = _paragraph_of(self._path, _labelled_lines())
        expected = " ".join(f"{label} {text}" for label, text in zip(LABELS, LABELLED_TEXTS))
        self.assertEqual(expected, paragraph)


if __name__ == "__main__":
    unittest.main()
