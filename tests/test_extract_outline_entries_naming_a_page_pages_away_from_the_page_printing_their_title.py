from __future__ import annotations

import tempfile
import unittest
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

PAGE_WIDTH = 432.0
PAGE_HEIGHT = 663.0
DESTINATION_Y = 36.0
SECTION_LEVEL = 1
CHAPTER_TITLE = "Desire and Recognition"
NOTES_TITLE = "Notes"
APPENDIX_TITLE = "Appendix"
PAGE_COUNT = 8
CHAPTER_PAGE = 1
NOTES_ENTRY_PAGE = 2
NOTES_PRINTED_PAGE = 5
APPENDIX_ENTRY_PAGE = 8
APPENDIX_PRINTED_PAGE = 6
PROSE = "The argument runs on from the page before and fills this page to its foot."
NOTE = "1 This line of argument is confirmed later, when labour is taken up."
TITLE_ROWS = (60.0, 72.0)
FIRST_ROWS = (80.0, 300.0)
SECOND_ROWS = (310.0, 600.0)


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            for _page in range(PAGE_COUNT):
                document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": 1, "to": pymupdf.Point(0, DESTINATION_Y)}
            document.set_toc([[SECTION_LEVEL, CHAPTER_TITLE, CHAPTER_PAGE, destination],
                              [SECTION_LEVEL, NOTES_TITLE, NOTES_ENTRY_PAGE, destination],
                              [SECTION_LEVEL, APPENDIX_TITLE, APPENDIX_ENTRY_PAGE, destination]])
            document.save(self._path)
        return self._path


def block(file_page: int, printed: tuple[str, str, tuple[float, float]]) -> Block:
    kind, text, (top, bottom) = printed
    return Block(file_page, kind, f"<p>{text}</p>", (40.0, top, 390.0, bottom), {}, f"/page/{file_page}/{top}")


def printed_pages() -> list[PageBlocks]:
    titled = {CHAPTER_PAGE: CHAPTER_TITLE, NOTES_PRINTED_PAGE: NOTES_TITLE, APPENDIX_PRINTED_PAGE: APPENDIX_TITLE}
    pages = []
    for file_page in range(1, PAGE_COUNT + 1):
        blocks = [block(file_page, (TEXT_KIND, PROSE, FIRST_ROWS))]
        if file_page in titled:
            blocks = [block(file_page, (HEADING_KIND, titled[file_page], TITLE_ROWS))] + blocks
        pages.append(PageBlocks(file_page, blocks + [block(file_page, (TEXT_KIND, NOTE, SECOND_ROWS))]))
    return pages


class TestOutlineEntriesNamingAPagePagesAwayFromThePagePrintingTheirTitle(unittest.TestCase):
    def _headings(self) -> list[Heading]:
        with tempfile.TemporaryDirectory() as directory:
            outline = Outline(OutlinedPdf(directory).write()).headings()
        work = WorkInputs(FakeLayer(), BlockHtml(FakeHyphens()), FakeFonts())
        inputs = StructureInputs(DocumentBlocks(printed_pages()), outline, WorkerReadings.none(), keep_everything())
        return [element for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_each_entry_opens_once(self) -> None:
        self.assertEqual([CHAPTER_TITLE, NOTES_TITLE, APPENDIX_TITLE], [heading.title for heading in self._headings()])

    def test_an_entry_naming_a_page_before_its_title_opens_on_the_later_page_printing_it(self) -> None:
        self.assertEqual(NOTES_PRINTED_PAGE, self._headings()[1].file_page)

    def test_an_entry_naming_a_page_after_its_title_opens_on_the_earlier_page_printing_it(self) -> None:
        self.assertEqual(APPENDIX_PRINTED_PAGE, self._headings()[2].file_page)


if __name__ == "__main__":
    unittest.main()
