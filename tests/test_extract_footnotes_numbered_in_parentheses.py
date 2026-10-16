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
NOTE_SIZE = 8.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0
BODY_HEAD = "Ce qui est rationnel, dit Hegel (1), par un concept qui"
BODY_TAIL = "ne se laisse pas encore déterminer."
NOTE = "(1) Voyez Hegel, Science de la logique, t. I, p. 12."
UNMARKED_BODY_HEAD = "Ce qui est rationnel, dit Hegel, par un concept qui"
JOINED_BODY = f"{BODY_HEAD} %% file p. 2 %% {BODY_TAIL}"


class ParenthesisedNotePdf:
    def __init__(self, path: Path, body_head: str, note_size: float) -> None:
        self._path = path
        self._body_head = body_head
        self._note_size = note_size

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            first.insert_text((LEFT, BODY_BASELINE), self._body_head, fontsize=BODY_SIZE, fontname=FONT)
            first.insert_text((LEFT, NOTE_BASELINE), NOTE, fontsize=self._note_size, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((LEFT, BODY_BASELINE), BODY_TAIL, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class EngineReading:
    def __init__(self, continues: bool, body_head: str) -> None:
        self._continues = continues
        self._body_head = body_head

    def pages(self) -> list[PageBlocks]:
        first = [self._block(1, TEXT_KIND, self._body_head), self._block(1, FOOTNOTE_KIND, NOTE)]
        return [PageBlocks(1, first), PageBlocks(2, [self._block(2, TEXT_KIND, BODY_TAIL)])]

    def _block(self, file_page: int, kind: str, text: str) -> Block:
        baseline = NOTE_BASELINE if kind == FOOTNOTE_KIND else BODY_BASELINE
        box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
        continued = self._continues and text == self._body_head
        return Block(file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{kind}/{baseline}", continued)


def written(continues: bool, body_head: str = BODY_HEAD, note_size: float = NOTE_SIZE) -> tuple[str, list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(ParenthesisedNotePdf(Path(directory) / "note.pdf", body_head, note_size).write())
        try:
            reading = DocumentBlocks(EngineReading(continues, body_head).pages())
            inputs = StructureInputs(reading, [], WorkerReadings.none(), keep_everything())
            structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
            text = NoteWriter().render(structure.elements(), structure.definitions()).text
            return text, [definition.text for definition in structure.definitions()]
        finally:
            layer.close()


class TestFootnotesNumberedInParentheses(unittest.TestCase):
    def test_a_note_numbered_in_parentheses_is_a_definition_when_the_body_runs_on_to_the_next_page(self) -> None:
        text, definitions = written(continues=True)
        self.assertEqual(([NOTE], True), (definitions, JOINED_BODY in text))

    def test_a_note_numbered_in_parentheses_is_a_definition_when_the_body_block_is_not_flagged_as_continuing(
            self) -> None:
        text, definitions = written(continues=False)
        self.assertEqual(([NOTE], False), (definitions, NOTE in text.split("# Notes")[0]))

    def test_a_note_numbered_in_parentheses_at_body_size_is_a_definition_when_the_body_raises_its_mark(self) -> None:
        _text, definitions = written(continues=False, note_size=BODY_SIZE)
        self.assertEqual([NOTE], definitions)

    def test_a_note_numbered_in_parentheses_at_note_size_is_a_definition_when_the_body_raises_no_mark(self) -> None:
        _text, definitions = written(continues=False, body_head=UNMARKED_BODY_HEAD)
        self.assertEqual([NOTE], definitions)


if __name__ == "__main__":
    unittest.main()
