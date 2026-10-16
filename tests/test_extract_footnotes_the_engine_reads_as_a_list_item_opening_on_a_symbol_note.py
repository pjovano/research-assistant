from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, LIST_ITEM_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.5
NOTE_SIZE = 9.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 432.0
PAGE_HEIGHT = 648.0
LEFT = 40.0
RIGHT = 390.0
LINE_ASCENT = 9.0
LINE_DESCENT = 4.0
BODY_BASELINE = 100.0
NOTE_BASELINES = (480.0, 492.0)
CONTINUATION_BASELINE = 80.0
SECOND_BODY_BASELINE = 140.0
SYMBOL = "*"
NUMERAL = "1"
BODY_OPENING = "In his works,"
BODY_MIDDLE = " Fichte says little of aesthetics."
SYMBOL_NOTE = "Kant is cited from the Academy edition."
NUMBERED_NOTE_OPENING = "A pioneer in the study was Pareyson; see New Essays on Fich-"
CONTINUATION = "te's later Jena Wissenschaftslehre, 2002."
NUMBERED_NOTE = "A pioneer in the study was Pareyson; see New Essays on Fich- te's later Jena Wissenschaftslehre, 2002."
SECOND_BODY = "The practical philosophy continues the meditations."
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


class ListItemNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            self._first_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            self._second_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            document.save(self._path)
        return self._path

    @staticmethod
    def _first_page(page) -> None:
        left = LEFT
        for text, size, rise in ((BODY_OPENING, BODY_SIZE, 0.0), (SYMBOL, MARK_SIZE, MARK_RISE),
                                 (BODY_MIDDLE, BODY_SIZE, 0.0), (NUMERAL, MARK_SIZE, MARK_RISE)):
            page.insert_text((left, BODY_BASELINE - rise), text, fontsize=size, fontname=FONT)
            left += pymupdf.get_text_length(text, FONT, size)
        for baseline, text in zip(NOTE_BASELINES, (f"{SYMBOL} {SYMBOL_NOTE}", f"{NUMERAL} {NUMBERED_NOTE_OPENING}")):
            page.insert_text((LEFT, baseline), text, fontsize=NOTE_SIZE, fontname=FONT)

    @staticmethod
    def _second_page(page) -> None:
        page.insert_text((LEFT, CONTINUATION_BASELINE), CONTINUATION, fontsize=NOTE_SIZE, fontname=FONT)
        page.insert_text((LEFT, SECOND_BODY_BASELINE), SECOND_BODY, fontsize=BODY_SIZE, fontname=FONT)


@dataclass(frozen=True)
class EngineRegion:
    kind: str
    first_baseline: float
    last_baseline: float

    def block(self, file_page: int, html: str) -> Block:
        box = (LEFT, self.first_baseline - LINE_ASCENT, RIGHT, self.last_baseline + LINE_DESCENT)
        return Block(file_page, self.kind, html, box, {}, f"/page/{file_page}/{self.kind}/{self.first_baseline}")


def engine_reading() -> list[PageBlocks]:
    body = f"<p>{BODY_OPENING}<sup>{SYMBOL}</sup>{BODY_MIDDLE}<sup>{NUMERAL}</sup></p>"
    notes = f"<li>{SYMBOL} {SYMBOL_NOTE} {NUMERAL} {NUMBERED_NOTE_OPENING}</li>"
    first = [EngineRegion(TEXT_KIND, BODY_BASELINE, BODY_BASELINE).block(1, body),
             EngineRegion(LIST_ITEM_KIND, NOTE_BASELINES[0], NOTE_BASELINES[-1]).block(1, notes)]
    continuation = EngineRegion(FOOTNOTE_KIND, CONTINUATION_BASELINE, CONTINUATION_BASELINE)
    second_body = EngineRegion(TEXT_KIND, SECOND_BODY_BASELINE, SECOND_BODY_BASELINE)
    second = [continuation.block(2, f"<p>{CONTINUATION}</p>"), second_body.block(2, f"<p>{SECOND_BODY}</p>")]
    return [PageBlocks(1, first), PageBlocks(2, second)]


class TestFootnotesTheEngineReadsAsAListItemOpeningOnASymbolNote(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(ListItemNotesPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = DEFINITION_RE.findall(self.text)

    def test_the_numbered_note_after_the_symbol_note_pairs_with_its_mark(self) -> None:
        self.assertIn(f"{BODY_MIDDLE}[^{NUMERAL}]", self.text)

    def test_the_unnumbered_text_atop_the_next_page_continues_the_numbered_note(self) -> None:
        self.assertIn((NUMERAL, NUMBERED_NOTE), self.definitions)

    def test_the_symbol_note_pairs_with_its_raised_symbol(self) -> None:
        labels = {text: label for label, text in self.definitions}
        self.assertIn(f"{BODY_OPENING}[^{labels[SYMBOL_NOTE]}]", self.text)

    def test_the_notes_are_not_written_into_the_body_as_a_list(self) -> None:
        self.assertNotIn(f"- {SYMBOL}", self.text)


if __name__ == "__main__":
    unittest.main()
