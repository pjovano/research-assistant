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
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
FIRST_BODY_BASELINE = 100.0
SECOND_BODY_BASELINE = 140.0
FIRST_NOTE_BASELINE = 480.0
SET_APART_BASELINE = 500.0
RUN_ON_BASELINE = 520.0
SECOND_NOTE_BASELINE = 540.0
FIRST_SENTENCE = "The argument is valid, but it proves too much."
SECOND_SENTENCE = "A second paragraph follows the first one."
FIRST_NOTE_OPENING = "The core of the analysis is:"
SET_APART_LINE = "s is in a state X such that X carries p"
RUN_ON_LINE = "which is treated as an extensional context."
SECOND_NOTE = "A second model of knowledge carries the same assumption."


@dataclass(frozen=True)
class MarkedLine:
    baseline: float
    sentence: str
    mark: str

    def draw_on(self, page) -> None:
        page.insert_text((LEFT, self.baseline), self.sentence, fontsize=BODY_SIZE, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(self.sentence, FONT, BODY_SIZE)
        page.insert_text((mark_left, self.baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)


class NoteSetApartPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            MarkedLine(FIRST_BODY_BASELINE, FIRST_SENTENCE, "13").draw_on(page)
            MarkedLine(SECOND_BODY_BASELINE, SECOND_SENTENCE, "14").draw_on(page)
            for baseline, text in self._note_lines():
                page.insert_text((LEFT, baseline), text, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _note_lines() -> list[tuple[float, str]]:
        return [(FIRST_NOTE_BASELINE, f"13 {FIRST_NOTE_OPENING}"), (SET_APART_BASELINE, SET_APART_LINE),
                (RUN_ON_BASELINE, RUN_ON_LINE), (SECOND_NOTE_BASELINE, f"14 {SECOND_NOTE}")]


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading() -> list[PageBlocks]:
    return [PageBlocks(1, [engine_block(TEXT_KIND, f"<p>{FIRST_SENTENCE}<sup>13</sup></p>", FIRST_BODY_BASELINE),
                           engine_block(TEXT_KIND, f"<p>{SECOND_SENTENCE}<sup>14</sup></p>", SECOND_BODY_BASELINE),
                           engine_block(FOOTNOTE_KIND, f"<p>13 {FIRST_NOTE_OPENING}</p>", FIRST_NOTE_BASELINE),
                           engine_block(TEXT_KIND, f"<p>{SET_APART_LINE}</p>", SET_APART_BASELINE),
                           engine_block(TEXT_KIND, f"<p>{RUN_ON_LINE}</p>", RUN_ON_BASELINE),
                           engine_block(FOOTNOTE_KIND, f"<p>14 {SECOND_NOTE}</p>", SECOND_NOTE_BASELINE)])]


class TestFootnoteRunningOnBelowALineSetApartAmongTheNotes(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(NoteSetApartPagePdf(Path(directory.name) / "page.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = structure.definitions()

    def test_the_note_carries_its_line_set_apart_and_its_run_on_text(self) -> None:
        self.assertEqual(f"{FIRST_NOTE_OPENING} {SET_APART_LINE} {RUN_ON_LINE}", self.definitions[0].text)

    def test_the_next_note_keeps_its_own_text(self) -> None:
        self.assertEqual(SECOND_NOTE, self.definitions[1].text)

    def test_the_body_holds_neither_the_line_set_apart_nor_the_run_on_text_above_the_note_under_its_numeral(
            self) -> None:
        body = self.text.split("[^13]:")[0]
        self.assertEqual((False, False), (SET_APART_LINE in body, RUN_ON_LINE in body))


if __name__ == "__main__":
    unittest.main()
