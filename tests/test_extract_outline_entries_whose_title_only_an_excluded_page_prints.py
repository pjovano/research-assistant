from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, FakeLayer, excluding
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.spans import PagePlace
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

SECTION_LEVEL = 1
EDITION_PREFACE = "Preface to This Edition"
VOLUME_TITLE = "Volume One: The Theory of Signs"
PREFACE = "Preface"
EDITION_PAGE = 1
HALF_TITLE_PAGE = 2
VOLUME_PAGE = 3
PAGE_COUNT = 3
PROSE = "The two volumes are here combined in one book, and their text is unchanged."
TITLE_ROWS = (60.0, 72.0)
PROSE_ROWS = (80.0, 300.0)


class VolumesPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "volumes.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            for _page in range(PAGE_COUNT):
                document.new_page()
            document.set_toc([[SECTION_LEVEL, EDITION_PREFACE, EDITION_PAGE],
                              [SECTION_LEVEL, VOLUME_TITLE, VOLUME_PAGE],
                              [SECTION_LEVEL, PREFACE, VOLUME_PAGE]])
            document.save(self._path)
        return self._path


def block(file_page: int, printed: tuple[str, str, tuple[float, float]]) -> Block:
    kind, text, (top, bottom) = printed
    return Block(file_page, kind, f"<p>{text}</p>", (40.0, top, 390.0, bottom), {}, f"/page/{file_page}/{top}")


def printed_pages() -> list[PageBlocks]:
    prose = (TEXT_KIND, PROSE, PROSE_ROWS)
    return [PageBlocks(EDITION_PAGE, [block(EDITION_PAGE, (HEADING_KIND, EDITION_PREFACE, TITLE_ROWS)),
                                      block(EDITION_PAGE, prose)]),
            PageBlocks(HALF_TITLE_PAGE, [block(HALF_TITLE_PAGE, (HEADING_KIND, VOLUME_TITLE, TITLE_ROWS))]),
            PageBlocks(VOLUME_PAGE, [block(VOLUME_PAGE, (HEADING_KIND, PREFACE, TITLE_ROWS)),
                                     block(VOLUME_PAGE, prose)])]


class TestOutlineEntriesWhoseTitleOnlyAnExcludedPagePrints(unittest.TestCase):
    def _headings(self) -> list[Heading]:
        with tempfile.TemporaryDirectory() as directory:
            outline = Outline(VolumesPdf(directory).write()).headings()
        work = WorkInputs(FakeLayer(), BlockHtml(FakeHyphens()), FakeFonts())
        policy = excluding(PagePlace(HALF_TITLE_PAGE), PagePlace(VOLUME_PAGE))
        inputs = StructureInputs(DocumentBlocks(printed_pages()), outline, WorkerReadings.none(), policy)
        return [element for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_the_entry_opens_in_the_outlines_order(self) -> None:
        self.assertEqual([EDITION_PREFACE, VOLUME_TITLE, PREFACE], [heading.title for heading in self._headings()])

    def test_the_entry_opens_on_the_page_it_names(self) -> None:
        pages = {heading.title: heading.file_page for heading in self._headings()}
        self.assertEqual(VOLUME_PAGE, pages.get(VOLUME_TITLE))


if __name__ == "__main__":
    unittest.main()
