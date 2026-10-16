from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TABLE_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
FILE_PAGE = 1
CELL_SIZE = 8.0
LINE_PITCH = 10.0
ROW_GAP = 8.0
FIRST_BASELINE = 100.0
COLUMN_LEFTS = (40.0, 100.0, 160.0)
TABLE_RIGHT = 280.0
HEADER = (("Step",), ("Example",), ("Objection",))
BODY = ((("(1) That p.",), ("I perceive", "an object."), ("We can only", "say that I", "think so.")),
        (("(2) It would", "not be", "possible."), ("I cannot", "perceive it."), ("The move", "meets", "counterexamples.")))
ROWS = (HEADER, *BODY)


def _cell_text(cell: tuple[str, ...]) -> str:
    return " ".join(cell)


def _row_height(row: tuple) -> float:
    return max(len(cell) for cell in row) * LINE_PITCH + ROW_GAP


def wrapped_table_pdf(path: Path) -> Path:
    with pymupdf.open() as document:
        page = document.new_page()
        top = FIRST_BASELINE
        for row in ROWS:
            for left, cell in zip(COLUMN_LEFTS, row):
                for position, line in enumerate(cell):
                    page.insert_text((left, top + position * LINE_PITCH), line, fontsize=CELL_SIZE, fontname=FONT)
            top += _row_height(row)
        document.save(path)
    return path


def engine_table(cells_per_row: int) -> DocumentBlocks:
    rows = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in _engine_cells(row, cells_per_row)) + "</tr>"
                   for row in ROWS)
    bottom = FIRST_BASELINE + sum(_row_height(row) for row in ROWS)
    box = (COLUMN_LEFTS[0] - 2.0, FIRST_BASELINE - LINE_PITCH, TABLE_RIGHT, bottom)
    table = Block(FILE_PAGE, TABLE_KIND, f"<table>{rows}</table>", box, {}, f"/page/{FILE_PAGE}/Table/0")
    return DocumentBlocks([PageBlocks(FILE_PAGE, [table])])


def _engine_cells(row: tuple, cells_per_row: int) -> list[str]:
    texts = [_cell_text(cell) for cell in row]
    return texts[:cells_per_row - 1] + [" ".join(texts[cells_per_row - 1:])]


class TestExtractBorderlessTablesWhoseWrappedCellsTheEngineRunsIntoFewerColumns(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._layer = TextLayer(wrapped_table_pdf(Path(directory.name) / "table.pdf"))
        self.addCleanup(self._layer.close)

    def _table_lines(self, cells_per_row: int) -> list[str]:
        inputs = StructureInputs(engine_table(cells_per_row), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(self._layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        return [line for line in text.splitlines() if line.startswith("|")]

    def test_a_table_the_engine_reads_in_fewer_columns_is_rebuilt_from_the_text_layers_cells(self) -> None:
        expected = ["| " + " | ".join(_cell_text(cell) for cell in row) + " |" for row in BODY]
        self.assertEqual(expected, self._table_lines(cells_per_row=2)[2:])

    def test_a_table_the_engine_reads_in_every_column_keeps_the_engines_cells(self) -> None:
        header = "| " + " | ".join(_cell_text(cell) for cell in HEADER) + " |"
        self.assertEqual(header, self._table_lines(cells_per_row=len(COLUMN_LEFTS))[0])


if __name__ == "__main__":
    unittest.main()
