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
TEXT_LEFT = 128.0
RIGHT = 380.0
BODY_SIZE = 8.5
HEADING_SIZE = 16.0
LINE_PITCH = 10.0
HEADING_BASELINE = 60.0
FIRST_ROW_BASELINE = 100.0
HEADING_TITLE = "Bibliography"
WRAPPED_LABELS = (("AB", ("Anna Abel, ed. 1965. Collected Papers on the Subject. 7 vols.", "Berlin: Verlag.")),
                  ("CD", ("Clara Dorn, trans. 1969. Selected Letters on Method. Second",
                          "edition. Oxford: Blackwell.")),
                  ("EF", ("Emil Fass and Gerd Hahn, ed. 1975. Studies in Logic and Proof",
                          "and Method. New York: Routledge.")))
GRID_ROWS = (("1990", "Abel", "Berlin"), ("1991", "Dorn", "Oxford"), ("1992", "Fass", "New York"))
GRID_COLUMN_LEFTS = (LEFT, 150.0, 250.0)


def _baseline(row: int) -> float:
    return FIRST_ROW_BASELINE + row * LINE_PITCH


def _block(kind: str, html: str, span: tuple[float, float]) -> Block:
    top, bottom = span
    return Block(FILE_PAGE, kind, html, (LEFT - 2.0, top, RIGHT + 2.0, bottom), {}, f"/page/{FILE_PAGE}/{kind}/{top}")


def _table_html(rows: list[tuple[str, ...]]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table>{body}</table>"


class BibliographyPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "bibliography.pdf"
        self._page = None

    def write_label_list(self) -> Path:
        return self._write(self._label_list)

    def write_grid(self) -> Path:
        return self._write(self._grid)

    def _write(self, draw_rows) -> Path:
        with pymupdf.open() as document:
            self._page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._page.insert_text((LEFT, HEADING_BASELINE), HEADING_TITLE, fontsize=HEADING_SIZE, fontname=FONT)
            draw_rows()
            document.save(self._path)
        return self._path

    def _label_list(self) -> None:
        row = 0
        for label, lines in WRAPPED_LABELS:
            self._text(LEFT, row, label)
            for line in lines:
                self._text(TEXT_LEFT, row, line)
                row += 1

    def _grid(self) -> None:
        for row, cells in enumerate(GRID_ROWS):
            for left, cell in zip(GRID_COLUMN_LEFTS, cells):
                self._text(left, row, cell)

    def _text(self, left: float, row: int, text: str) -> None:
        self._page.insert_text((left, _baseline(row)), text, fontsize=BODY_SIZE, fontname=FONT)


def engine_reading(table_html: str, rows: int) -> DocumentBlocks:
    heading = _block(HEADING_KIND, f"<h1>{HEADING_TITLE}</h1>", (HEADING_BASELINE - HEADING_SIZE, HEADING_BASELINE + 4))
    table = _block(TABLE_KIND, table_html, (FIRST_ROW_BASELINE - LINE_PITCH, _baseline(rows - 1) + 3))
    return DocumentBlocks([PageBlocks(FILE_PAGE, [heading, table])])


def engine_grid_of_the_label_list() -> str:
    return _table_html([(label, *_split_at_the_first_stop(first)) for label, (first, _rest) in WRAPPED_LABELS])


def _split_at_the_first_stop(line: str) -> tuple[str, str]:
    cut = line.index(".") + 1
    return line[:cut], line[cut:]


class TestEntryListsSettingAWrappedLabelListTheEngineReadsAsATable(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._pdf = BibliographyPagePdf(Path(directory.name))

    def _paragraphs(self, pdf_path: Path, blocks: DocumentBlocks) -> list[str]:
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text.strip().split("\n\n")

    def test_each_label_opens_an_entry_holding_its_wrapped_reference_whole(self) -> None:
        rows = sum(len(lines) for _label, lines in WRAPPED_LABELS)
        blocks = engine_reading(engine_grid_of_the_label_list(), rows)
        paragraphs = self._paragraphs(self._pdf.write_label_list(), blocks)
        expected = [" ".join([label, *lines]) for label, lines in WRAPPED_LABELS]
        self.assertEqual(expected, [" ".join(paragraph.split()) for paragraph in paragraphs[-len(expected):]])

    def test_a_table_setting_its_cells_in_three_columns_stays_a_table(self) -> None:
        blocks = engine_reading(_table_html(list(GRID_ROWS)), len(GRID_ROWS))
        paragraphs = self._paragraphs(self._pdf.write_grid(), blocks)
        self.assertEqual("| 1990 | Abel | Berlin |", paragraphs[-1].splitlines()[0])


if __name__ == "__main__":
    unittest.main()
