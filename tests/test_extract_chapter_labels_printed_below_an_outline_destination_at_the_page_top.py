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

CLOSING = "Thus words are conventional signs of thoughts, and characters are conventional signs of words."
LABEL = "CHAPTER 5"
TITLE_LINE = "Ideas considered according to their composition or simplicity"
OUTLINE_TITLE = f"5. {TITLE_LINE}"
OPENING = "The remark we made in passing in chapter 2 provides an opportunity to explain abstractions."
LEFT = 72.0
RIGHT = 500.0
BODY_SIZE = 10.0
LABEL_SIZE = 12.0
FIRST_BASELINE = 90.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
LINES = ((TEXT_KIND, CLOSING, BODY_SIZE), (HEADING_KIND, LABEL, LABEL_SIZE), (TEXT_KIND, TITLE_LINE, BODY_SIZE),
         (TEXT_KIND, OPENING, BODY_SIZE))


class MidPageChapterPdf:
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
        tag = "h2" if kind == HEADING_KIND else "p"
        blocks.append(Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}"))
    return DocumentBlocks([PageBlocks(1, blocks)])


class TestChapterLabelsPrintedBelowAnOutlineDestinationAtThePageTop(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _written(self) -> list[str]:
        pdf_path = MidPageChapterPdf(self._directory / "mid-page.pdf").write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(document_blocks(), Outline(pdf_path).headings(), WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [element.title if isinstance(element, Heading) else element.text
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_the_heading_opens_at_the_label_below_the_text_above_it(self) -> None:
        self.assertEqual([CLOSING, OUTLINE_TITLE, OPENING], self._written())


if __name__ == "__main__":
    unittest.main()
