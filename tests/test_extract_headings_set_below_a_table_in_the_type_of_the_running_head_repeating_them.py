from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TABLE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

HEADER_KIND = "PageHeader"
SECTION_TITLE = "The hierarchy of justification"
CELLS = ("Mineness", "Relation")
OPENING = "This complex picture of action gives rise to an obvious problem."
LEFT = 72.0
TYPE_SIZE = 10.0
RUNNING_HEAD_BASELINE = 42.0
TABLE_BASELINE = 90.0
TITLE_BASELINE = 300.0
OPENING_BASELINE = 340.0
CELL_WIDTH = 120.0
RUNNING_HEAD_BOX = (70.0, 32.0, 300.0, 45.0)
TABLE_BOX = (70.0, 70.0, 500.0, 280.0)
TITLE_BOX = (70.0, 288.0, 300.0, 304.0)
OPENING_BOX = (70.0, 328.0, 500.0, 344.0)
RUNNING_HEADED_PAGES = (2, 3)
TABLE_HTML = "<table><tr>" + "".join(f"<td>{cell}</td>" for cell in CELLS) + "</tr></table>"


class TablePagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for column, cell in enumerate(CELLS):
                page.insert_text((LEFT + column * CELL_WIDTH, TABLE_BASELINE), cell, fontsize=TYPE_SIZE)
            page.insert_text((LEFT, TITLE_BASELINE), SECTION_TITLE, fontsize=TYPE_SIZE)
            page.insert_text((LEFT, OPENING_BASELINE), OPENING, fontsize=TYPE_SIZE)
            for _file_page in RUNNING_HEADED_PAGES:
                page = document.new_page()
                page.insert_text((LEFT, RUNNING_HEAD_BASELINE), SECTION_TITLE, fontsize=TYPE_SIZE)
                page.insert_text((LEFT, OPENING_BASELINE), OPENING, fontsize=TYPE_SIZE)
            document.set_toc([[1, SECTION_TITLE, 1]])
            document.save(self._path)
        return self._path


def printed(file_page: int, blocks: list[tuple[str, str, tuple]]) -> PageBlocks:
    return PageBlocks(file_page, [Block(file_page, kind, html, box, {}, f"/page/{file_page}/{index}")
                                  for index, (kind, html, box) in enumerate(blocks)])


def document_blocks() -> DocumentBlocks:
    opening = (TEXT_KIND, f"<p>{OPENING}</p>", OPENING_BOX)
    table_page = printed(1, [(TABLE_KIND, TABLE_HTML, TABLE_BOX), (HEADING_KIND, f"<h2>{SECTION_TITLE}</h2>", TITLE_BOX),
                             opening])
    headed = [printed(file_page, [(HEADER_KIND, f"<p>{SECTION_TITLE}</p>", RUNNING_HEAD_BOX), opening])
              for file_page in RUNNING_HEADED_PAGES]
    return DocumentBlocks([table_page] + headed)


class TestHeadingsSetBelowATableInTheTypeOfTheRunningHeadRepeatingThem(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _elements(self) -> list:
        pdf_path = TablePagePdf(self._directory / "table-page.pdf").write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        furniture = WorkFurniture(layer)
        blocks = furniture.refiled(document_blocks())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), furniture=blocks.furniture_texts,
                          furniture_profile=furniture.profile(blocks))
        inputs = StructureInputs(blocks, Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        return [element for element in NoteStructure(work, inputs).elements() if element.file_page == 1]

    def test_a_heading_set_below_a_table_opens_after_the_table(self) -> None:
        elements = self._elements()
        heading = next(index for index, element in enumerate(elements) if isinstance(element, Heading))
        table = next(index for index, element in enumerate(elements) if CELLS[0] in getattr(element, "text", ""))
        self.assertLess(table, heading)

    def test_a_heading_set_below_a_table_keeps_the_outline_title(self) -> None:
        titles = [element.title for element in self._elements() if isinstance(element, Heading)]
        self.assertEqual([SECTION_TITLE], titles)


if __name__ == "__main__":
    unittest.main()
