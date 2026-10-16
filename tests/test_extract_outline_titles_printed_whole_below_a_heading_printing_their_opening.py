from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, excluding
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Heading as OutlineHeading
from _extract.readings import WorkerReadings
from _extract.spans import PagePlace
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

HEADER_KIND = "PageHeader"
WORK_TITLE = "The Given"
OPENING = "THE GIVEN"
CHAPTER_TITLE = "The given, and the Myth of the Given"
PROSE = "The argument of this essay turns on what experience presents to the mind."
LEFT = 72.0
RUNNING_HEAD_SIZE = 9.0
DISPLAY_SIZE = 16.0
TITLE_SIZE = 11.0
BODY_SIZE = 10.0
RUNNING_HEAD_BASELINE = 42.0
OPENING_BASELINE = 100.0
TITLE_BASELINE = 200.0
PROSE_BASELINE = 230.0
RUNNING_HEAD_BOX = (70.0, 32.0, 200.0, 45.0)
OPENING_BOX = (70.0, 84.0, 200.0, 104.0)
TITLE_BOX = (70.0, 190.0, 300.0, 203.0)
PROSE_BOX = (70.0, 220.0, 500.0, 234.0)
RUNNING_HEADED_PAGES = (2, 3)
TITLE_ENTRY = OutlineHeading(1, CHAPTER_TITLE, 1, TITLE_BOX[1])


class ChapterPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, OPENING_BASELINE), OPENING, fontsize=DISPLAY_SIZE)
            page.insert_text((LEFT, TITLE_BASELINE), CHAPTER_TITLE, fontsize=TITLE_SIZE)
            page.insert_text((LEFT, PROSE_BASELINE), PROSE, fontsize=BODY_SIZE)
            for _file_page in RUNNING_HEADED_PAGES:
                page = document.new_page()
                page.insert_text((LEFT, RUNNING_HEAD_BASELINE), WORK_TITLE, fontsize=RUNNING_HEAD_SIZE)
                page.insert_text((LEFT, PROSE_BASELINE), PROSE, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path


def printed(file_page: int, blocks: list[tuple[str, str, tuple]]) -> PageBlocks:
    return PageBlocks(file_page, [Block(file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{index}")
                                  for index, (kind, text, box) in enumerate(blocks)])


def document_blocks() -> DocumentBlocks:
    prose = (TEXT_KIND, PROSE, PROSE_BOX)
    opening = printed(1, [(HEADING_KIND, OPENING, OPENING_BOX), (HEADING_KIND, CHAPTER_TITLE, TITLE_BOX), prose])
    headed = [printed(file_page, [(HEADER_KIND, WORK_TITLE, RUNNING_HEAD_BOX), prose])
              for file_page in RUNNING_HEADED_PAGES]
    return DocumentBlocks([opening] + headed)


class TestOutlineTitlesPrintedWholeBelowAHeadingPrintingTheirOpening(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        layer = TextLayer(ChapterPdf(directory / "chapter.pdf").write())
        self.addCleanup(layer.close)
        furniture = WorkFurniture(layer)
        blocks = furniture.refiled(document_blocks())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), work_title=WORK_TITLE,
                          furniture=blocks.furniture_texts, furniture_profile=furniture.profile(blocks))
        before_the_title = excluding(PagePlace(1), PagePlace.of_block(document_blocks().pages[0].blocks[1]))
        inputs = StructureInputs(blocks, [TITLE_ENTRY], WorkerReadings.none(), before_the_title)
        self.headings = [element.title for element in NoteStructure(work, inputs).elements()
                         if isinstance(element, Heading)]

    def test_the_outline_title_opens_where_the_page_prints_it_whole(self) -> None:
        self.assertEqual([CHAPTER_TITLE], self.headings)


if __name__ == "__main__":
    unittest.main()
