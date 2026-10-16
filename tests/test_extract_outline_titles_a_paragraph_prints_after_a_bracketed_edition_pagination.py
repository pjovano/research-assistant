from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, FakeLayer, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

PAGE_WIDTH = 420.0
PAGE_HEIGHT = 595.0
DESTINATION_DEPTH = 36.0
SECTION_LEVEL = 1
FIRST_PAGE = 1
SECOND_PAGE = 2
THIRD_PAGE = 3
FIRST_TITLE = "8"
SECOND_TITLE = "9"
CARRIED_PROSE = "for they could not depend on more, but all depend on the points aforesaid."
FIRST_SECTION = "[10] 8 · The eighth section opens below the prose carried over."
SECOND_SECTION = "[20] 9 · The ninth section opens in the middle of the page before its entry's page."
SECOND_SECTION_SET_WITH_A_LETTER = "[181<sup>a</sup>1] 9 · The ninth section opens in the middle of its page."
RUN_ON_PROSE = "depend upon the principles of geometry and the conclusions that follow from these."


@dataclass(frozen=True)
class PageBand:
    file_page: int
    top: float
    bottom: float


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_entries_on(self, first_page: int, second_page: int) -> Path:
        with pymupdf.open() as document:
            for _page in range(THIRD_PAGE):
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": pymupdf.LINK_GOTO, "to": pymupdf.Point(72, DESTINATION_DEPTH)}
            document.set_toc([[SECTION_LEVEL, FIRST_TITLE, first_page, destination],
                              [SECTION_LEVEL, SECOND_TITLE, second_page, destination]])
            document.save(self._path)
        return self._path


def placed(html: str, band: PageBand) -> Block:
    box = (40.0, band.top, 380.0, band.bottom)
    return Block(band.file_page, TEXT_KIND, f"<p>{html}</p>", box, {}, f"/page/{band.file_page}/{band.top}")


def sections_opening_mid_page(second_section: str) -> list[PageBlocks]:
    first = [placed(CARRIED_PROSE, PageBand(FIRST_PAGE, 59.0, 90.0)),
             placed(FIRST_SECTION, PageBand(FIRST_PAGE, 104.0, 306.0))]
    second = [placed(CARRIED_PROSE, PageBand(SECOND_PAGE, 59.0, 90.0)),
              placed(second_section, PageBand(SECOND_PAGE, 318.0, 525.0))]
    third = [placed(RUN_ON_PROSE, PageBand(THIRD_PAGE, 59.0, 527.0))]
    return [PageBlocks(FIRST_PAGE, first), PageBlocks(SECOND_PAGE, second), PageBlocks(THIRD_PAGE, third)]


class TestOutlineTitlesAParagraphPrintsAfterABracketedEditionPagination(unittest.TestCase):
    def _elements(self, second_entry_page: int, second_section: str) -> list[tuple[int, str]]:
        with tempfile.TemporaryDirectory() as directory:
            outline = Outline(OutlinedPdf(directory).with_entries_on(FIRST_PAGE, second_entry_page)).headings()
        work = WorkInputs(FakeLayer(), BlockHtml(FakeHyphens()), FakeFonts())
        inputs = StructureInputs(DocumentBlocks(sections_opening_mid_page(second_section)), outline,
                                 WorkerReadings.none(), keep_everything())
        elements = NoteStructure(work, inputs).elements()
        return [(element.file_page, element.title if isinstance(element, Heading) else element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_an_entry_on_the_page_of_its_paragraph_opens_above_that_paragraph(self) -> None:
        elements = self._elements(SECOND_PAGE, SECOND_SECTION)
        self.assertEqual([(SECOND_PAGE, CARRIED_PROSE), (SECOND_PAGE, SECOND_TITLE), (SECOND_PAGE, SECOND_SECTION)],
                         elements[3:6])

    def test_an_entry_naming_the_page_after_its_paragraph_opens_above_that_paragraph(self) -> None:
        elements = self._elements(THIRD_PAGE, SECOND_SECTION)
        self.assertEqual([(SECOND_PAGE, CARRIED_PROSE), (SECOND_PAGE, SECOND_TITLE), (SECOND_PAGE, SECOND_SECTION),
                          (THIRD_PAGE, RUN_ON_PROSE)], elements[3:])

    def test_a_pagination_carrying_a_raised_letter_reads_as_one(self) -> None:
        elements = self._elements(SECOND_PAGE, SECOND_SECTION_SET_WITH_A_LETTER)
        self.assertEqual([(SECOND_PAGE, CARRIED_PROSE), (SECOND_PAGE, SECOND_TITLE)], elements[3:5])


if __name__ == "__main__":
    unittest.main()
