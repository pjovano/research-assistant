from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 600.0
MARKED_SENTENCE = "This is because you say that the divine sign keeps coming to you."
MARK = "1"
NOTE = "See the earlier dialogue."
ANSWERING_FOOT = f"{MARK}. {NOTE}"
UNANSWERING_FOOT = f"2. {NOTE}"


class MarkedPagePdf:
    def __init__(self, path: Path, foot: str) -> None:
        self._path = path
        self._foot = foot

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, BODY_BASELINE), MARKED_SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            mark_left = LEFT + pymupdf.get_text_length(MARKED_SENTENCE, FONT, BODY_SIZE)
            page.insert_text((mark_left, BODY_BASELINE - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
            page.insert_text((LEFT, NOTE_BASELINE), self._foot, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading(foot: str) -> list[PageBlocks]:
    return [PageBlocks(1, [engine_block(TEXT_KIND, f"<p>{MARKED_SENTENCE}<sup>{MARK}</sup></p>", BODY_BASELINE),
                           engine_block(HEADING_KIND, f"<h2>{foot}</h2>", NOTE_BASELINE)])]


class TestFootnotesReadAsAHeadingAtTheFootOfAPageWithoutNotes(unittest.TestCase):
    def built(self, foot: str) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(MarkedPagePdf(Path(directory.name) / "marked.pdf", foot).write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading(foot)), [], WorkerReadings.none(), keep_everything())
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def rendered(self, foot: str) -> str:
        structure = self.built(foot)
        return NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_a_heading_opening_on_the_numeral_of_a_raised_mark_is_the_marks_footnote(self) -> None:
        structure = self.built(ANSWERING_FOOT)
        self.assertEqual([NOTE], [definition.text for definition in structure.definitions()])

    def test_the_raised_mark_links_the_footnote(self) -> None:
        self.assertIn(f"{MARKED_SENTENCE}[^1]", self.rendered(ANSWERING_FOOT))

    def test_a_heading_opening_on_a_numeral_no_mark_raises_stays_out_of_the_notes(self) -> None:
        self.assertEqual([], self.built(UNANSWERING_FOOT).definitions())


if __name__ == "__main__":
    unittest.main()
