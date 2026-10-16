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
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
HEADING_SIZE = 14.0
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 360.0
HEADING_BASELINE = 80.0
BODY_BASELINE = 120.0
LINE_HALF_HEIGHT = 6.0
PRINTED_TITLE = "Preface to the 1st edition [2000]"
MARKED_UP_TITLE = "Preface to the 1<sup>st</sup> edition [2000]"
COMPARISON_TITLE = "Why a < b and c > d"
SENTENCE = "This volume offers a partly rewritten version of the dissertation."


class PrefacePdf:
    def __init__(self, path: Path, outline_title: str) -> None:
        self._path = path
        self._outline_title = outline_title

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, HEADING_BASELINE), PRINTED_TITLE, fontsize=HEADING_SIZE, fontname=FONT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            document.set_toc([[1, self._outline_title, 1]])
            document.save(self._path)
        return self._path

    @staticmethod
    def blocks() -> DocumentBlocks:
        heading = Block(1, HEADING_KIND, f"<h3>{PRINTED_TITLE}</h3>", _box(HEADING_BASELINE, HEADING_SIZE), {}, "/h")
        body = Block(1, TEXT_KIND, f"<p>{SENTENCE}</p>", _box(BODY_BASELINE, BODY_SIZE), {}, "/p")
        return DocumentBlocks([PageBlocks(1, [heading, body])])


def _box(baseline: float, size: float) -> tuple[float, float, float, float]:
    return (LEFT, baseline - size - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


class TestOutlineTitlesCarryingMarkupTags(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _pdf_path(self, outline_title: str) -> Path:
        return PrefacePdf(self._directory / "preface.pdf", outline_title).write()

    def test_the_outline_reads_a_title_without_its_markup_tags(self) -> None:
        headings = Outline(self._pdf_path(MARKED_UP_TITLE)).headings()
        self.assertEqual([PRINTED_TITLE], [heading.title for heading in headings])

    def test_the_outline_keeps_angle_brackets_that_open_no_tag(self) -> None:
        headings = Outline(self._pdf_path(COMPARISON_TITLE)).headings()
        self.assertEqual([COMPARISON_TITLE], [heading.title for heading in headings])

    def test_a_heading_the_page_prints_under_a_marked_up_outline_title_is_written_once(self) -> None:
        pdf_path = self._pdf_path(MARKED_UP_TITLE)
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(PrefacePdf.blocks(), Outline(pdf_path).headings(), WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        written = [element.title if isinstance(element, Heading) else element.text for element in elements
                   if isinstance(element, (Heading, Paragraph))]
        self.assertEqual([PRINTED_TITLE, SENTENCE], written)


if __name__ == "__main__":
    unittest.main()
