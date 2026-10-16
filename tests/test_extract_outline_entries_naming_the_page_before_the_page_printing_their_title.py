from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, FakeLayer, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

PAGE_WIDTH = 432.0
PAGE_HEIGHT = 663.0
DESTINATION_Y = 36.0
FIRST_TITLE = "THE FIRST SECTION"
SECTION_TITLE = "THE SECOND SECTION"
SECTION_LEVEL = 1
FIRST_PAGE = 1
SECOND_PAGE = 2
FIRST_PROSE = "The first section fills the page its outline entry names."
RUN_ON_PROSE = "The first section runs on to the head of the next page."
OPENING_PROSE = "The second section opens below the title the next page prints."


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_second_entry_on(self, file_page: int) -> Path:
        with pymupdf.open() as document:
            for _page in range(SECOND_PAGE):
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": 1, "to": pymupdf.Point(0, DESTINATION_Y)}
            document.set_toc([[SECTION_LEVEL, FIRST_TITLE, FIRST_PAGE, destination],
                              [SECTION_LEVEL, SECTION_TITLE, file_page, destination]])
            document.save(self._path)
        return self._path


class PrintedPage:
    def __init__(self, file_page: int) -> None:
        self._file_page = file_page
        self._blocks: list[Block] = []

    def printing(self, kind: str, text: str, rows: tuple[float, float]) -> PrintedPage:
        top, bottom = rows
        self._blocks.append(Block(self._file_page, kind, f"<p>{text}</p>", (40.0, top, 390.0, bottom), {},
                                  f"/page/{self._file_page}/{kind}/{top}"))
        return self

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(self._file_page, list(self._blocks))


def title_below_run_on_prose_on_the_second_page() -> list[PageBlocks]:
    first = (PrintedPage(FIRST_PAGE)
             .printing(HEADING_KIND, FIRST_TITLE, (60.0, 72.0))
             .printing(TEXT_KIND, FIRST_PROSE, (80.0, 600.0)))
    second = (PrintedPage(SECOND_PAGE)
              .printing(TEXT_KIND, RUN_ON_PROSE, (58.0, 80.0))
              .printing(HEADING_KIND, SECTION_TITLE, (98.0, 110.0))
              .printing(TEXT_KIND, OPENING_PROSE, (121.0, 600.0)))
    return [first.blocks, second.blocks]


class TestOutlineEntriesNamingThePageBeforeThePagePrintingTheirTitle(unittest.TestCase):
    def _elements(self) -> list:
        with tempfile.TemporaryDirectory() as directory:
            outline = Outline(OutlinedPdf(directory).with_second_entry_on(FIRST_PAGE)).headings()
        work = WorkInputs(FakeLayer(), BlockHtml(FakeHyphens()), FakeFonts())
        inputs = StructureInputs(DocumentBlocks(title_below_run_on_prose_on_the_second_page()), outline,
                                 WorkerReadings.none(), keep_everything())
        return NoteStructure(work, inputs).elements()

    def _headings(self) -> list[Heading]:
        return [element for element in self._elements() if isinstance(element, Heading)]

    def test_an_entry_whose_title_opens_the_next_page_opens_once(self) -> None:
        self.assertEqual([FIRST_TITLE, SECTION_TITLE], [heading.title for heading in self._headings()])

    def test_an_entry_whose_title_opens_the_next_page_opens_there_at_its_outline_level(self) -> None:
        heading = self._headings()[-1]
        self.assertEqual((SECOND_PAGE, SECTION_LEVEL), (heading.file_page, heading.level))

    def test_an_entry_whose_title_opens_the_next_page_opens_below_the_prose_run_on_above_it(self) -> None:
        texts = [element.title if isinstance(element, Heading) else element.text
                 for element in self._elements() if isinstance(element, (Heading, Paragraph))]
        self.assertEqual([FIRST_TITLE, FIRST_PROSE, RUN_ON_PROSE, SECTION_TITLE, OPENING_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
