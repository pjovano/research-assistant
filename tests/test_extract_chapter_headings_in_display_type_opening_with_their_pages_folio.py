from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.runningheads import FurnitureProfile
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
DISPLAY_SIZE = 16.0
RUNNING_HEAD_SIZE = 9.0
BODY_SIZE = 10.0
LEFT = 48.0
RIGHT = 382.0
HEADING_BASELINE = 90.0
BODY_BASELINE = 140.0
LINE_HALF_HEIGHT = 6.0
FOLIO = "1"
CHAPTER_HEADING = f"{FOLIO} Introduction"
RUNNING_HEAD = "Introduction 2"
RUNNING_HEAD_SHAPE = "introduction"
SENTENCE = "That certain kinds of marks and noises have meanings is a very striking fact."
DESTINATION_NEAR_THE_FOOT = 700.0


class ChapterPagePdf:
    def __init__(self, path: Path, heading_size: float) -> None:
        self._path = path
        self._heading_size = heading_size

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, HEADING_BASELINE), CHAPTER_HEADING, fontsize=self._heading_size, fontname=FONT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            destination = {"kind": pymupdf.LINK_GOTO, "to": pymupdf.Point(0, DESTINATION_NEAR_THE_FOOT)}
            document.set_toc([[1, CHAPTER_HEADING, 1, destination]])
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        heading = Block(1, HEADING_KIND, f"<h1>{CHAPTER_HEADING}</h1>", _box(HEADING_BASELINE, self._heading_size), {},
                        "/page/1/heading")
        body = Block(1, TEXT_KIND, f"<p>{SENTENCE}</p>", _box(BODY_BASELINE, BODY_SIZE), {}, "/page/1/text")
        return DocumentBlocks([PageBlocks(1, [heading, body])])


def _box(baseline: float, size: float) -> tuple[float, float, float, float]:
    return (LEFT, baseline - size - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


class TestChapterHeadingsInDisplayTypeOpeningWithTheirPagesFolio(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, heading_size: float) -> list[str]:
        pdf = ChapterPagePdf(self._directory / "chapter.pdf", heading_size)
        pdf_path = pdf.write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), folios={1: FOLIO}, furniture=[RUNNING_HEAD],
                          furniture_profile=FurnitureProfile({RUNNING_HEAD_SHAPE: RUNNING_HEAD_SIZE}))
        inputs = StructureInputs(pdf.blocks(), Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        return [element.title if isinstance(element, Heading) else element.text
                for element in NoteStructure(work, inputs).elements() if isinstance(element, (Heading, Paragraph))]

    def test_a_chapter_heading_in_display_type_opening_with_the_folio_opens_where_the_page_prints_it(self) -> None:
        self.assertEqual([CHAPTER_HEADING, SENTENCE], self._written(DISPLAY_SIZE))

    def test_a_line_in_running_head_type_opening_with_the_folio_is_taken_for_the_running_head(self) -> None:
        self.assertEqual([SENTENCE, CHAPTER_HEADING], self._written(RUNNING_HEAD_SIZE))


if __name__ == "__main__":
    unittest.main()
