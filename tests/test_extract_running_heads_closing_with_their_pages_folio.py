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
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
BODY_SIZE = 10.0
LEFT = 48.0
RIGHT = 382.0
HEAD_BASELINE = 60.0
BODY_BASELINE = 90.0
LINE_HALF_HEIGHT = 6.0
FOLIO = "119"
OTHER_NUMBER = "7"
RUNNING_HEAD_WORDS = "§ 4. THE RANGE OF A SENTENCE"
SENTENCE = "Here we shall discuss definitions which make use of extensional concepts only."


class HeadedPagePdf:
    def __init__(self, path: Path, head: str) -> None:
        self._path = path
        self._head = head

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, HEAD_BASELINE), self._head, fontsize=BODY_SIZE, fontname=FONT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        head = Block(1, HEADING_KIND, f"<h4>{self._head}</h4>", _box(HEAD_BASELINE), {}, "/page/1/heading")
        body = Block(1, TEXT_KIND, f"<p>{SENTENCE}</p>", _box(BODY_BASELINE), {}, "/page/1/text")
        return DocumentBlocks([PageBlocks(1, [head, body])])


def _box(baseline: float) -> tuple[float, float, float, float]:
    return (LEFT, baseline - BODY_SIZE - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


class TestRunningHeadsClosingWithTheirPagesFolio(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, head: str) -> list[str]:
        pdf = HeadedPagePdf(self._directory / "headed.pdf", head)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), folios={1: FOLIO})
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        return [element.title if isinstance(element, Heading) else element.text
                for element in NoteStructure(work, inputs).elements() if isinstance(element, (Heading, Paragraph))]

    def test_a_line_at_the_page_top_closing_with_the_folio_is_taken_for_the_running_head(self) -> None:
        self.assertEqual([SENTENCE], self._written(f"{RUNNING_HEAD_WORDS} {FOLIO}"))

    def test_a_line_at_the_page_top_closing_with_another_number_stays_a_heading(self) -> None:
        heading = f"{RUNNING_HEAD_WORDS} {OTHER_NUMBER}"
        self.assertEqual([heading, SENTENCE], self._written(heading))


if __name__ == "__main__":
    unittest.main()
