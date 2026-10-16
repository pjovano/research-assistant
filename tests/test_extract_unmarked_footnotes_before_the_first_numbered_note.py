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
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0
BODY_HEAD = "The argument of this paper begins with a claim that"
BODY_TAIL = "every reader will grant at once."
SYMBOL_NOTE = "* I thank the referees of this journal."
NOTE_WITHOUT_ITS_NUMBER = "Ich danke den Gutachtern dieser Zeitschrift."
JOINED_BODY = f"{BODY_HEAD} %% file p. 2 %% {BODY_TAIL}"


class TwoPagePdf:
    def __init__(self, path: Path, note: str) -> None:
        self._path = path
        self._note = note

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            first.insert_text((LEFT, BODY_BASELINE), BODY_HEAD, fontsize=FONT_SIZE, fontname=FONT)
            first.insert_text((LEFT, NOTE_BASELINE), self._note, fontsize=FONT_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((LEFT, BODY_BASELINE), BODY_TAIL, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(file_page: int, kind: str, text: str) -> Block:
    baseline = NOTE_BASELINE if kind == FOOTNOTE_KIND else BODY_BASELINE
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    continued = text == BODY_HEAD
    return Block(file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{kind}/{baseline}", continued)


def engine_reading(note: str) -> list[PageBlocks]:
    first = [engine_block(1, TEXT_KIND, BODY_HEAD), engine_block(1, FOOTNOTE_KIND, note)]
    return [PageBlocks(1, first), PageBlocks(2, [engine_block(2, TEXT_KIND, BODY_TAIL)])]


def written(note: str) -> tuple[list[str], list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(TwoPagePdf(Path(directory) / "notes.pdf", note).write())
        try:
            inputs = StructureInputs(DocumentBlocks(engine_reading(note)), [], WorkerReadings.none(), keep_everything())
            structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
            text = NoteWriter().render(structure.elements(), structure.definitions()).text
            return text.strip().split("\n\n"), [definition.text for definition in structure.definitions()]
        finally:
            layer.close()


class TestUnmarkedFootnotesBeforeTheFirstNumberedNote(unittest.TestCase):
    def test_a_symbol_marked_note_is_a_definition(self) -> None:
        _paragraphs, definitions = written(SYMBOL_NOTE)
        self.assertEqual([SYMBOL_NOTE], definitions)

    def test_a_note_that_lost_its_number_is_a_definition(self) -> None:
        _paragraphs, definitions = written(NOTE_WITHOUT_ITS_NUMBER)
        self.assertEqual([NOTE_WITHOUT_ITS_NUMBER], definitions)

    def test_a_body_paragraph_crossing_the_page_break_above_a_symbol_marked_note_stays_whole(self) -> None:
        paragraphs, _definitions = written(SYMBOL_NOTE)
        self.assertIn(JOINED_BODY, paragraphs)


if __name__ == "__main__":
    unittest.main()
