from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TABLE_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
FILE_PAGE = 1
PAGE_WIDTH, PAGE_HEIGHT = 432.0, 648.0
LEFT = 54.0
MEANING_LEFT = 150.0
RIGHT = 380.0
BODY_SIZE = 8.5
HEADING_SIZE = 16.0
LINE_PITCH = 10.0
HEADING_BASELINE = 60.0
FIRST_ROW_BASELINE = 100.0
HEADING_TITLE = "Notation"
BIBLIOGRAPHY_TITLE = "References"
NOTATION_ROWS = (("w, w', w''", ("variables of the truth value type.",)),
                 ("a, b, c", ("formulas.",)),
                 ("t(x/s)", ("the result of substituting s at each free occurrence of",
                             "x in t, renaming bound variables where needed.")))
PREMISE_ROWS = (("MaN", ("Mortal can be said of all men.",)),
                ("MoO", ("Mortal cannot be said of Enoch and Elijah.",)),
                ("NoO", ("Man cannot be said of Enoch and Elijah.",)))


def _baseline(row: int) -> float:
    return FIRST_ROW_BASELINE + row * LINE_PITCH


def _block(kind: str, html: str, span: tuple[float, float]) -> Block:
    top, bottom = span
    return Block(FILE_PAGE, kind, html, (LEFT - 2.0, top, RIGHT + 2.0, bottom), {}, f"/page/{FILE_PAGE}/{kind}/{top}")


def two_column_table_pdf(path: Path, title: str, table_rows: tuple) -> Path:
    with pymupdf.open() as document:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text((LEFT, HEADING_BASELINE), title, fontsize=HEADING_SIZE, fontname=FONT)
        row = 0
        for symbol, meaning in table_rows:
            page.insert_text((LEFT, _baseline(row)), symbol, fontsize=BODY_SIZE, fontname=FONT)
            for line in meaning:
                page.insert_text((MEANING_LEFT, _baseline(row)), line, fontsize=BODY_SIZE, fontname=FONT)
                row += 1
        document.save(path)
    return path


def engine_reading(title: str, table_rows: tuple) -> DocumentBlocks:
    rows = sum(len(meaning) for _symbol, meaning in table_rows)
    cells = "".join(f"<tr><td>{symbol}</td><td>{' '.join(meaning)}</td></tr>" for symbol, meaning in table_rows)
    heading = _block(HEADING_KIND, f"<h1>{title}</h1>", (HEADING_BASELINE - HEADING_SIZE, HEADING_BASELINE + 4))
    table = _block(TABLE_KIND, f"<table>{cells}</table>", (FIRST_ROW_BASELINE - LINE_PITCH, _baseline(rows - 1) + 3))
    return DocumentBlocks([PageBlocks(FILE_PAGE, [heading, table])])


class TestExtractTwoColumnTablesTheEngineReads(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _first_line_of_the_table(self, title: str, table_rows: tuple) -> str:
        layer = TextLayer(two_column_table_pdf(self._directory / "table.pdf", title, table_rows))
        self.addCleanup(layer.close)
        inputs = StructureInputs(engine_reading(title, table_rows), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        return text.strip().split("\n\n")[-1].splitlines()[0]

    def test_a_table_whose_second_column_wraps_stays_a_table(self) -> None:
        first_line = self._first_line_of_the_table(HEADING_TITLE, NOTATION_ROWS)
        self.assertEqual(f"| {NOTATION_ROWS[0][0]} | {NOTATION_ROWS[0][1][0]} |", first_line)

    def test_a_table_of_one_line_rows_under_a_bibliography_heading_stays_a_table(self) -> None:
        first_line = self._first_line_of_the_table(BIBLIOGRAPHY_TITLE, PREMISE_ROWS)
        self.assertEqual(f"| {PREMISE_ROWS[0][0]} | {PREMISE_ROWS[0][1][0]} |", first_line)


if __name__ == "__main__":
    unittest.main()
