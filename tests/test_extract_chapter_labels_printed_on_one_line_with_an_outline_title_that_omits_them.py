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
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

LABEL = "CHAPTER 2"
OUTLINE_TITLE = "The Function of Philosophy"
PRINTED_LINE = f"{LABEL} THE FUNCTION OF PHILOSOPHY"
OPENING = "Among the superstitions from which we are freed is the view that philosophy builds a system."
LEFT = 72.0
RIGHT = 500.0
BODY_SIZE = 10.0
TITLE_SIZE = 14.0
FIRST_BASELINE = 90.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
LINES = ((HEADING_KIND, PRINTED_LINE, TITLE_SIZE), (TEXT_KIND, OPENING, BODY_SIZE))


class LabelledTitlePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, (_kind, text, size) in enumerate(LINES):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=size)
            document.set_toc([[1, OUTLINE_TITLE, 1]])
            document.save(self._path)
        return self._path


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def document_blocks() -> DocumentBlocks:
    blocks = []
    for row, (kind, text, size) in enumerate(LINES):
        box = (LEFT, _baseline(row) - size - LINE_HALF_HEIGHT, RIGHT, _baseline(row) + LINE_HALF_HEIGHT)
        tag = "h1" if kind == HEADING_KIND else "p"
        blocks.append(Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}"))
    return DocumentBlocks([PageBlocks(1, blocks)])


class TestChapterLabelsPrintedOnOneLineWithAnOutlineTitleThatOmitsThem(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _written(self) -> list[tuple[str, int, str]]:
        pdf_path = LabelledTitlePdf(self._directory / "labelled.pdf").write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(document_blocks(), Outline(pdf_path).headings(), WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [(type(element).__name__, element.level, element.title) if isinstance(element, Heading)
                else (type(element).__name__, 0, element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_the_label_opens_a_heading_of_the_outline_titles_level_above_it(self) -> None:
        expected = [(Heading.__name__, 1, LABEL), (Heading.__name__, 1, OUTLINE_TITLE), (Paragraph.__name__, 0, OPENING)]
        self.assertEqual(expected, self._written())


if __name__ == "__main__":
    unittest.main()
