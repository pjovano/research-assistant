from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

HEADER_KIND = "PageHeader"
SECTION_TITLE = "Bibliography"
ENTRY = "Adorno, T. (2002). Aesthetic Theory. New York: Continuum."
LEFT = 72.0
RUNNING_HEAD_SIZE = 9.0
TITLE_SIZE = 16.0
SIZE_A_FIFTH_ABOVE_THE_RUNNING_HEAD = 11.0
SIZE_SHORT_OF_A_FIFTH_ABOVE_THE_RUNNING_HEAD = 10.5
BODY_SIZE = 10.0
RUNNING_HEAD_BASELINE = 42.0
TITLE_BASELINE = 90.0
ENTRY_BASELINE = 130.0
RUNNING_HEAD_BOX = (70.0, 32.0, 200.0, 45.0)
TITLE_BOX = (70.0, 72.0, 200.0, 94.0)
ENTRY_BOX = (70.0, 118.0, 500.0, 134.0)
RUNNING_HEADED_PAGES = (2, 3)


class BackMatterPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, title_size: float) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, TITLE_BASELINE), SECTION_TITLE, fontsize=title_size)
            page.insert_text((LEFT, ENTRY_BASELINE), ENTRY, fontsize=BODY_SIZE)
            for _file_page in RUNNING_HEADED_PAGES:
                page = document.new_page()
                page.insert_text((LEFT, RUNNING_HEAD_BASELINE), SECTION_TITLE, fontsize=RUNNING_HEAD_SIZE)
                page.insert_text((LEFT, ENTRY_BASELINE), ENTRY, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path


def printed(file_page: int, blocks: list[tuple[str, str, tuple]]) -> PageBlocks:
    return PageBlocks(file_page, [Block(file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{index}")
                                  for index, (kind, text, box) in enumerate(blocks)])


def document_blocks() -> DocumentBlocks:
    entry = (TEXT_KIND, ENTRY, ENTRY_BOX)
    opening = printed(1, [(HEADING_KIND, SECTION_TITLE, TITLE_BOX), entry])
    headed = [printed(file_page, [(HEADER_KIND, SECTION_TITLE, RUNNING_HEAD_BOX), entry])
              for file_page in RUNNING_HEADED_PAGES]
    return DocumentBlocks([opening] + headed)


class TestSectionTitlesSetLargerThanTheRunningHeadRepeatingThem(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _heading_titles(self, title_size: float) -> list[str]:
        layer = TextLayer(BackMatterPdf(self._directory / "back-matter.pdf").write(title_size))
        self.addCleanup(layer.close)
        furniture = WorkFurniture(layer)
        blocks = furniture.refiled(document_blocks())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), furniture=blocks.furniture_texts,
                          furniture_profile=furniture.profile(blocks))
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        return [element.title for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_a_title_set_larger_than_the_running_head_printing_its_words_opens_a_heading(self) -> None:
        self.assertEqual([SECTION_TITLE], self._heading_titles(TITLE_SIZE))

    def test_a_title_set_a_fifth_larger_than_the_running_head_opens_a_heading(self) -> None:
        self.assertEqual([SECTION_TITLE], self._heading_titles(SIZE_A_FIFTH_ABOVE_THE_RUNNING_HEAD))

    def test_a_line_set_short_of_a_fifth_larger_than_the_running_head_is_dropped_as_a_running_head(self) -> None:
        self.assertEqual([], self._heading_titles(SIZE_SHORT_OF_A_FIFTH_ABOVE_THE_RUNNING_HEAD))

    def test_a_line_set_in_the_running_heads_own_type_is_still_dropped_as_a_running_head(self) -> None:
        self.assertEqual([], self._heading_titles(RUNNING_HEAD_SIZE))


if __name__ == "__main__":
    unittest.main()
