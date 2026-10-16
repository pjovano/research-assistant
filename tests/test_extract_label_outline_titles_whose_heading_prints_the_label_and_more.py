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
RIGHT = 400.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
LABEL = "BOOK I"
REFERENCED_HEADING = "BOOK I [100a20]"
CHAPTER_LABEL = "Chapter 1"
CHAPTER_TITLE = "Setting the Stage"
SENTENCE = "Our treatise proposes to find a line of inquiry whereby we shall be able to reason."


class LabelledPagePdf:
    def __init__(self, path: Path, headings: list[str]) -> None:
        self._path = path
        self._lines = [(HEADING_KIND, text, HEADING_SIZE) for text in headings] + [(TEXT_KIND, SENTENCE, BODY_SIZE)]

    def write(self, outline_title: str) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, (_kind, text, size) in enumerate(self._lines):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=size, fontname=FONT)
            page_top = {"kind": pymupdf.LINK_GOTO, "to": pymupdf.Point(0, 0)}
            document.set_toc([[1, outline_title, 1, page_top]])
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_engine_block(row, line) for row, line in enumerate(self._lines)])])


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def _engine_block(row: int, line: tuple[str, str, float]) -> Block:
    kind, text, size = line
    baseline = _baseline(row)
    box = (LEFT, baseline - size - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)
    tag = "h2" if kind == HEADING_KIND else "p"
    return Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}")


class TestLabelOutlineTitlesWhoseHeadingPrintsTheLabelAndMore(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, headings: list[str], outline_title: str) -> list[str]:
        pdf = LabelledPagePdf(self._directory / "labelled.pdf", headings)
        pdf_path = pdf.write(outline_title)
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [element.title if isinstance(element, Heading) else element.text for element in elements
                if isinstance(element, (Heading, Paragraph))]

    def test_a_heading_printing_the_label_and_a_reference_is_written_once_as_printed(self) -> None:
        self.assertEqual([REFERENCED_HEADING, SENTENCE], self._written([REFERENCED_HEADING], LABEL))

    def test_a_title_printed_below_a_bare_label_is_joined_to_the_label(self) -> None:
        written = self._written([CHAPTER_LABEL, CHAPTER_TITLE], CHAPTER_LABEL)
        self.assertEqual([f"{CHAPTER_LABEL}: {CHAPTER_TITLE}", SENTENCE], written)


if __name__ == "__main__":
    unittest.main()
