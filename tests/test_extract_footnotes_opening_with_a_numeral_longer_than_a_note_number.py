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
BODY = "The argument of this paper begins with a claim every reader will grant."
YEAR_NOTE = "1998 Subject Classification: 18A40, 18B25."
NUMBERED_NOTE = "12 See the appendix for the proof."


class OnePagePdf:
    def __init__(self, path: Path, note: str) -> None:
        self._path = path
        self._note = note

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, BODY_BASELINE), BODY, fontsize=FONT_SIZE, fontname=FONT)
            page.insert_text((LEFT, NOTE_BASELINE), self._note, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(kind: str, text: str) -> Block:
    baseline = NOTE_BASELINE if kind == FOOTNOTE_KIND else BODY_BASELINE
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, f"<p>{text}</p>", box, {}, f"/page/1/{kind}/{baseline}", False)


def definitions_of(note: str) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(OnePagePdf(Path(directory) / "note.pdf", note).write())
        try:
            page = PageBlocks(1, [engine_block(TEXT_KIND, BODY), engine_block(FOOTNOTE_KIND, note)])
            inputs = StructureInputs(DocumentBlocks([page]), [], WorkerReadings.none(), keep_everything())
            structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
            NoteWriter().render(structure.elements(), structure.definitions())
            return [definition.text for definition in structure.definitions()]
        finally:
            layer.close()


class TestFootnotesOpeningWithANumeralLongerThanANoteNumber(unittest.TestCase):
    def test_a_note_opening_with_a_four_digit_numeral_keeps_the_numeral_whole(self) -> None:
        self.assertEqual([YEAR_NOTE], definitions_of(YEAR_NOTE))

    def test_a_note_opening_with_a_note_number_is_printed_with_its_number(self) -> None:
        self.assertEqual(["12. See the appendix for the proof."], definitions_of(NUMBERED_NOTE))


if __name__ == "__main__":
    unittest.main()
