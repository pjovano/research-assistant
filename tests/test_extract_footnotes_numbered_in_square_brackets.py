from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
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
NOTE_SIZE = 7.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
FIRST_BODY_BASELINE = 100.0
SECOND_BODY_BASELINE = 140.0
FIRST_NOTE_BASELINE = 560.0
SECOND_NOTE_BASELINE = 580.0
FIRST_SENTENCE = "Experience is the obligatory starting point."
SECOND_SENTENCE = "No problem of irreconcilability arises."
FIRST_NOTE = "For a standard argument see the second chapter."
SECOND_NOTE = "The thought was not new."


@dataclass(frozen=True)
class MarkedLine:
    baseline: float
    sentence: str
    mark: str

    def draw_on(self, page) -> None:
        page.insert_text((LEFT, self.baseline), self.sentence, fontsize=BODY_SIZE, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(self.sentence, FONT, BODY_SIZE)
        page.insert_text((mark_left, self.baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)


class BracketNumeralPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            MarkedLine(FIRST_BODY_BASELINE, FIRST_SENTENCE, "3").draw_on(page)
            MarkedLine(SECOND_BODY_BASELINE, SECOND_SENTENCE, "4").draw_on(page)
            notes = [(FIRST_NOTE_BASELINE, f"[3] {FIRST_NOTE}"), (SECOND_NOTE_BASELINE, f"[4] {SECOND_NOTE}")]
            for baseline, text in notes:
                page.insert_text((LEFT, baseline), text, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading() -> list[PageBlocks]:
    return [PageBlocks(1, [engine_block(TEXT_KIND, f"<p>{FIRST_SENTENCE}<sup>3</sup></p>", FIRST_BODY_BASELINE),
                           engine_block(TEXT_KIND, f"<p>{SECOND_SENTENCE}<sup>4</sup></p>", SECOND_BODY_BASELINE),
                           engine_block(FOOTNOTE_KIND, f"<p><sup>[3]</sup> {FIRST_NOTE}</p>", FIRST_NOTE_BASELINE),
                           engine_block(FOOTNOTE_KIND, f"<p><sup>[4]</sup> {SECOND_NOTE}</p>", SECOND_NOTE_BASELINE)])]


class TestFootnotesNumberedInSquareBrackets(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(BracketNumeralPagePdf(Path(directory.name) / "page.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = structure.definitions()

    def test_each_note_takes_the_numeral_its_brackets_enclose(self) -> None:
        self.assertEqual([(3, FIRST_NOTE), (4, SECOND_NOTE)],
                         [(definition.label, definition.text) for definition in self.definitions])

    def test_each_mark_links_to_its_note(self) -> None:
        body = self.text.split("[^3]:")[0]
        self.assertEqual((True, True), (f"{FIRST_SENTENCE}[^3]" in body, f"{SECOND_SENTENCE}[^4]" in body))


if __name__ == "__main__":
    unittest.main()
