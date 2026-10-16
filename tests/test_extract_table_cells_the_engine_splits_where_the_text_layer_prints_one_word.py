from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TABLE_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Verbatim
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
ITALIC_FONT = "heit"
CELL_SIZE = 8.0
SUBSCRIPT_SIZE = 6.8
SUBSCRIPT_DROP = 1.4
LEFT = 100.0
COLUMN_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_PITCH = 16.0
HALF_ROW = 8.0
HEADER = ("A", "B", "(0, 0)", "(1, 1)")
LABELS = (("a", "1", "b", "1"), ("a", "1", "b", "2"), ("a", "2", "b", "1"))
OUTCOMES = (("1", "0"), ("0", "1"), ("1", "1"))
SPLIT_HEADER = ("", "A", "", "B", "(0, 0)", "(1, 1)")


@dataclass(frozen=True)
class LabelledTablePdf:
    path: Path
    subscript_gap: float

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for column, text in enumerate(HEADER):
                page.insert_text((self._left_of(column), FIRST_BASELINE), text, fontsize=CELL_SIZE, fontname=FONT)
            for row in range(len(LABELS)):
                self._draw_row(page, row)
            document.save(self.path)
        return self.path

    def blocks(self) -> DocumentBlocks:
        rows = [_table_row("th", SPLIT_HEADER)] + [_table_row("td", labels + outcomes)
                                                   for labels, outcomes in zip(LABELS, OUTCOMES)]
        bottom = FIRST_BASELINE + len(LABELS) * ROW_PITCH + HALF_ROW
        box = (LEFT - HALF_ROW, FIRST_BASELINE - ROW_PITCH, LEFT + len(HEADER) * COLUMN_PITCH, bottom)
        table = Block(1, TABLE_KIND, f"<table>{''.join(rows)}</table>", box, {}, "/page/1/Table/0")
        return DocumentBlocks([PageBlocks(1, [table])])

    def _draw_row(self, page, row: int) -> None:
        baseline = FIRST_BASELINE + (row + 1) * ROW_PITCH
        labels = LABELS[row]
        for column, label in enumerate(zip(labels[::2], labels[1::2])):
            self._draw_label(page, (self._left_of(column), baseline), label)
        for column, outcome in enumerate(OUTCOMES[row], start=len(labels) // 2):
            page.insert_text((self._left_of(column), baseline), outcome, fontsize=CELL_SIZE, fontname=FONT)

    def _draw_label(self, page, origin: tuple[float, float], label: tuple[str, str]) -> None:
        left, baseline = origin
        letter, index = label
        page.insert_text((left, baseline), letter, fontsize=CELL_SIZE, fontname=ITALIC_FONT)
        index_left = left + pymupdf.get_text_length(letter, ITALIC_FONT, CELL_SIZE) + self.subscript_gap
        page.insert_text((index_left, baseline + SUBSCRIPT_DROP), index, fontsize=SUBSCRIPT_SIZE, fontname=FONT)

    @staticmethod
    def _left_of(column: int) -> float:
        return LEFT + column * COLUMN_PITCH


def _table_row(tag: str, cells: tuple[str, ...]) -> str:
    return "<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>"


class TestTableCellsTheEngineSplitsWhereTheTextLayerPrintsOneWord(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _table_rows(self, subscript_gap: float) -> list[str]:
        pdf = LabelledTablePdf(self._directory / "table.pdf", subscript_gap)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        table, = [element.text for element in elements if isinstance(element, Verbatim)]
        return table.splitlines()

    def test_a_label_printed_as_one_word_fills_one_cell(self) -> None:
        self.assertEqual("| a1 | b1 | 1 | 0 |", self._table_rows(0.0)[2])

    def test_the_header_names_one_column_per_joined_pair(self) -> None:
        self.assertEqual("| A | B | (0, 0) | (1, 1) |", self._table_rows(0.0)[0])

    def test_cells_the_text_layer_prints_a_column_apart_stay_apart(self) -> None:
        self.assertEqual("| a | 1 | b | 1 | 1 | 0 |", self._table_rows(COLUMN_PITCH / 4)[2])


if __name__ == "__main__":
    unittest.main()
