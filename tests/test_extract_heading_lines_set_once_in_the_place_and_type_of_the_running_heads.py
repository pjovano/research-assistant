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
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

ONCE_PRINTED_LINE = "THE PRECEDING LECTURE"
RUNNING_HEAD = "THE PRESENT LECTURE"
BODY = "The argument of the lecture runs on across this page without a break."
LEFT = 72.0
RIGHT = 400.0
HEAD_SIZE = 9.0
DISPLAY_SIZE = 16.0
BODY_SIZE = 11.0
HEAD_BASELINE = 40.0
BODY_BASELINE = 80.0
LINE_HALF_HEIGHT = 4.0
RUNNING_HEADED_PAGES = (2, 3)
UNHEADED_PAGES = (4, 5)


class LecturePagesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, first_line_size: float, unheaded_pages: tuple[int, ...]) -> Path:
        with pymupdf.open() as document:
            self._page(document, ONCE_PRINTED_LINE, first_line_size)
            for _file_page in RUNNING_HEADED_PAGES:
                self._page(document, RUNNING_HEAD, HEAD_SIZE)
            for _file_page in unheaded_pages:
                document.new_page().insert_text((LEFT, BODY_BASELINE), BODY, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _page(document, head: str, head_size: float) -> None:
        page = document.new_page()
        page.insert_text((LEFT, HEAD_BASELINE), head, fontsize=head_size, fontname="hebo")
        page.insert_text((LEFT, BODY_BASELINE), BODY, fontsize=BODY_SIZE)


def _box(baseline: float, size: float) -> tuple[float, float, float, float]:
    return (LEFT - 2.0, baseline - size - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


def printed_page(file_page: int, head: str, head_size: float) -> PageBlocks:
    head_block = Block(file_page, HEADING_KIND, f"<p>{head}</p>", _box(HEAD_BASELINE, head_size), {},
                       f"/page/{file_page}/head")
    body = Block(file_page, TEXT_KIND, f"<p>{BODY}</p>", _box(BODY_BASELINE, BODY_SIZE), {}, f"/page/{file_page}/body")
    return PageBlocks(file_page, [head_block, body])


def unheaded_page(file_page: int) -> PageBlocks:
    body = Block(file_page, TEXT_KIND, f"<p>{BODY}</p>", _box(BODY_BASELINE, BODY_SIZE), {}, f"/page/{file_page}/body")
    return PageBlocks(file_page, [body])


def document_blocks(first_line_size: float, unheaded_pages: tuple[int, ...]) -> DocumentBlocks:
    headed = [printed_page(file_page, RUNNING_HEAD, HEAD_SIZE) for file_page in RUNNING_HEADED_PAGES]
    unheaded = [unheaded_page(file_page) for file_page in unheaded_pages]
    return DocumentBlocks([printed_page(1, ONCE_PRINTED_LINE, first_line_size)] + headed + unheaded)


class TestHeadingLinesSetOnceInThePlaceAndTypeOfTheRunningHeads(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _heading_titles(self, first_line_size: float, unheaded_pages: tuple[int, ...] = ()) -> list[str]:
        layer = TextLayer(LecturePagesPdf(self._directory / "lectures.pdf").write(first_line_size, unheaded_pages))
        self.addCleanup(layer.close)
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts())
        blocks = document_blocks(first_line_size, unheaded_pages)
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        return [element.title for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_a_line_printed_once_in_the_running_heads_place_and_type_is_dropped_as_a_running_head(self) -> None:
        self.assertNotIn(ONCE_PRINTED_LINE, self._heading_titles(HEAD_SIZE))

    def test_a_line_in_the_running_heads_place_set_in_display_type_stays_a_heading(self) -> None:
        self.assertIn(ONCE_PRINTED_LINE, self._heading_titles(DISPLAY_SIZE))

    def test_a_line_in_the_place_of_a_wording_repeated_atop_no_more_than_half_the_pages_stays_a_heading(self) -> None:
        self.assertIn(ONCE_PRINTED_LINE, self._heading_titles(HEAD_SIZE, UNHEADED_PAGES))


if __name__ == "__main__":
    unittest.main()
