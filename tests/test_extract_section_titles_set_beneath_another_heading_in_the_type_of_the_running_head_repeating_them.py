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
PART_TITLE = "APPENDIX"
SECTION_TITLE = "§ 7. Closing Remarks"
RUNNING_HEAD = "§ 7. CLOSING REMARKS"
ENTRY = "These remarks concern either particular terms or general questions of terminology."
LEFT = 72.0
TYPE_SIZE = 10.0
RUNNING_HEAD_BASELINE = 42.0
UPPER_BASELINE = 60.0
LOWER_BASELINE = 90.0
ENTRY_BASELINE = 130.0
LINE_HALF_HEIGHT = 6.0
RIGHT = 400.0
RUNNING_HEADED_PAGES = (2, 3)


class SectionPagesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, opening_lines: list[tuple[float, str]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for baseline, line in opening_lines:
                page.insert_text((LEFT, baseline), line, fontsize=TYPE_SIZE)
            page.insert_text((LEFT, ENTRY_BASELINE), ENTRY, fontsize=TYPE_SIZE)
            for _file_page in RUNNING_HEADED_PAGES:
                page = document.new_page()
                page.insert_text((LEFT, RUNNING_HEAD_BASELINE), RUNNING_HEAD, fontsize=TYPE_SIZE)
                page.insert_text((LEFT, ENTRY_BASELINE), ENTRY, fontsize=TYPE_SIZE)
            document.save(self._path)
        return self._path


def _box(baseline: float) -> tuple[float, float, float, float]:
    return (LEFT - 2.0, baseline - TYPE_SIZE - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


def printed(file_page: int, blocks: list[tuple[str, str, float]]) -> PageBlocks:
    return PageBlocks(file_page, [Block(file_page, kind, f"<p>{text}</p>", _box(baseline), {},
                                        f"/page/{file_page}/{index}")
                                  for index, (kind, text, baseline) in enumerate(blocks)])


def document_blocks(opening_lines: list[tuple[float, str]]) -> DocumentBlocks:
    entry = (TEXT_KIND, ENTRY, ENTRY_BASELINE)
    headings = [(HEADING_KIND, line, baseline) for baseline, line in opening_lines]
    opening = printed(1, headings + [entry])
    headed = [printed(file_page, [(HEADER_KIND, RUNNING_HEAD, RUNNING_HEAD_BASELINE), entry])
              for file_page in RUNNING_HEADED_PAGES]
    return DocumentBlocks([opening] + headed)


class TestSectionTitlesSetBeneathAnotherHeadingInTheTypeOfTheRunningHeadRepeatingThem(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _heading_titles(self, opening_lines: list[tuple[float, str]]) -> list[str]:
        layer = TextLayer(SectionPagesPdf(self._directory / "sections.pdf").write(opening_lines))
        self.addCleanup(layer.close)
        furniture = WorkFurniture(layer)
        blocks = furniture.refiled(document_blocks(opening_lines))
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), furniture=blocks.furniture_texts,
                          furniture_profile=furniture.profile(blocks))
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        return [element.title for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_a_title_beneath_another_heading_printing_the_running_heads_words_opens_a_heading(self) -> None:
        opening_lines = [(UPPER_BASELINE, PART_TITLE), (LOWER_BASELINE, SECTION_TITLE)]
        self.assertEqual([PART_TITLE, SECTION_TITLE], self._heading_titles(opening_lines))

    def test_a_title_at_the_page_top_printing_the_running_heads_words_is_dropped_as_a_running_head(self) -> None:
        self.assertEqual([], self._heading_titles([(UPPER_BASELINE, SECTION_TITLE)]))


if __name__ == "__main__":
    unittest.main()
