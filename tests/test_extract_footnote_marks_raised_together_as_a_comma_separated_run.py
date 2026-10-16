from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY_BASELINE = 100.0
FIRST_NOTE_BASELINE = 580.0
SECOND_NOTE_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0
SENTENCE = "If this outcome is to be avoided, then the argument is invalid."
MARK_RUN = ("13", ",", "14")
FIRST_NOTE = "The core of the analysis is a fallacy of intension."
SECOND_NOTE = "A second model of knowledge carries the same assumption."
RUN_HTML = f"<p>{SENTENCE}<sup>13, 14</sup></p>"


class MarkRunPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            self._raise_the_run(page, LEFT + pymupdf.get_text_length(SENTENCE, FONT, BODY_SIZE))
            page.insert_text((LEFT, FIRST_NOTE_BASELINE), f"13 {FIRST_NOTE}", fontsize=BODY_SIZE, fontname=FONT)
            page.insert_text((LEFT, SECOND_NOTE_BASELINE), f"14 {SECOND_NOTE}", fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _raise_the_run(page, left: float) -> None:
        for piece in MARK_RUN:
            page.insert_text((left, BODY_BASELINE - MARK_RISE), piece, fontsize=MARK_SIZE, fontname=FONT)
            left += pymupdf.get_text_length(piece, FONT, MARK_SIZE)


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading() -> list[PageBlocks]:
    return [PageBlocks(1, [engine_block(TEXT_KIND, RUN_HTML, BODY_BASELINE),
                           engine_block(FOOTNOTE_KIND, f"<p>13 {FIRST_NOTE}</p>", FIRST_NOTE_BASELINE),
                           engine_block(FOOTNOTE_KIND, f"<p>14 {SECOND_NOTE}</p>", SECOND_NOTE_BASELINE)])]


class TestFootnoteMarksRaisedTogetherAsACommaSeparatedRun(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(MarkRunPagePdf(Path(directory.name) / "page.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = structure.definitions()

    def test_each_number_of_the_run_references_its_own_footnote_by_its_printed_numeral(self) -> None:
        self.assertIn(f"{SENTENCE}[^13][^14]", self.text)

    def test_the_run_leaves_no_raised_markup_in_the_body(self) -> None:
        self.assertNotIn("<sup>", self.text)

    def test_each_footnote_of_the_run_is_a_marked_definition(self) -> None:
        self.assertEqual([(FIRST_NOTE, True), (SECOND_NOTE, True)],
                         [(definition.text, definition.marked) for definition in self.definitions])


if __name__ == "__main__":
    unittest.main()
