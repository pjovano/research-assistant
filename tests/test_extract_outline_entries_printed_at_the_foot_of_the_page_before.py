from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, FakeLayer, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
DESTINATION_Y = 28.0
FIRST_TITLE = "THE FIRST SECTION"
SECTION_TITLE = "THE SECOND SECTION"
SECTION_LEVEL = 1
FIRST_PAGE = 1
SECOND_PAGE = 2
CLOSING_PROSE = "The first section closes above the title that the page prints at its foot."
OPENING_PROSE = "The second section opens with this sentence at the foot of the page."
RUN_ON_PROSE = "The second section carries on over the page its outline entry names."


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_entry_on(self, file_page: int) -> Path:
        with pymupdf.open() as document:
            for _page in range(SECOND_PAGE):
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": 1, "to": pymupdf.Point(0, DESTINATION_Y)}
            document.set_toc([[SECTION_LEVEL, FIRST_TITLE, FIRST_PAGE, destination],
                              [SECTION_LEVEL, SECTION_TITLE, file_page, destination]])
            document.save(self._path)
        return self._path


@dataclass(frozen=True)
class PageBand:
    file_page: int
    top: float
    bottom: float


def placed(kind: str, text: str, band: PageBand) -> Block:
    box = (40.0, band.top, 360.0, band.bottom)
    return Block(band.file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{band.file_page}/{kind}/{band.top}")


def title_at_the_foot_of_the_first_page() -> list[PageBlocks]:
    first = [placed(HEADING_KIND, FIRST_TITLE, PageBand(FIRST_PAGE, 60.0, 72.0)),
             placed(TEXT_KIND, CLOSING_PROSE, PageBand(FIRST_PAGE, 80.0, 540.0)),
             placed(HEADING_KIND, SECTION_TITLE, PageBand(FIRST_PAGE, 567.0, 581.0)),
             placed(TEXT_KIND, OPENING_PROSE, PageBand(FIRST_PAGE, 587.0, 617.0))]
    second = [placed(TEXT_KIND, RUN_ON_PROSE, PageBand(SECOND_PAGE, 60.0, 615.0))]
    return [PageBlocks(FIRST_PAGE, first), PageBlocks(SECOND_PAGE, second)]


class TestOutlineEntriesPrintedAtTheFootOfThePageBefore(unittest.TestCase):
    def _headings(self) -> list[Heading]:
        with tempfile.TemporaryDirectory() as directory:
            outline = Outline(OutlinedPdf(directory).with_entry_on(SECOND_PAGE)).headings()
        work = WorkInputs(FakeLayer(), BlockHtml(FakeHyphens()), FakeFonts())
        inputs = StructureInputs(DocumentBlocks(title_at_the_foot_of_the_first_page()), outline,
                                 WorkerReadings.none(), keep_everything())
        return [element for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_an_entry_whose_title_closes_the_page_before_its_destination_opens_once(self) -> None:
        self.assertEqual([FIRST_TITLE, SECTION_TITLE], [heading.title for heading in self._headings()])

    def test_an_entry_whose_title_closes_the_page_before_its_destination_opens_there_at_its_outline_level(
            self) -> None:
        heading = self._headings()[-1]
        self.assertEqual((FIRST_PAGE, SECTION_LEVEL), (heading.file_page, heading.level))


if __name__ == "__main__":
    unittest.main()
