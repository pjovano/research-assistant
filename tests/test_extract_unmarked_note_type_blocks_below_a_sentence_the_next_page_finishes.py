from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 11.0
NOTE_SIZE = 8.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0
BROKEN_OFF_BODY = "Locke defines the person as a being that can consider itself as itself,"
FINISHED_BODY = "Locke defines the person as a being that can consider itself as itself."
NEXT_PAGE_BODY = "the same thinking thing in different times and places."
AUTHORS_NOTE = "This survey draws on our earlier work on the history of the self."
RUNNING_FOOT = "Theories of the Self"
SENTENCE_RUN_ON = f"{BROKEN_OFF_BODY} %% file p. 2 %% {NEXT_PAGE_BODY}"


class FootOfThePagePdf:
    def __init__(self, path: Path, first_body: str, foot: str) -> None:
        self._path = path
        self._first_body = first_body
        self._foot = foot

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            first.insert_text((LEFT, BODY_BASELINE), self._first_body, fontsize=BODY_SIZE, fontname=FONT)
            first.insert_text((LEFT, NOTE_BASELINE), self._foot, fontsize=NOTE_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((LEFT, BODY_BASELINE), NEXT_PAGE_BODY, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def text_block(file_page: int, text: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(file_page, TEXT_KIND, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{TEXT_KIND}/{baseline}")


def engine_reading(first_body: str, foot: str) -> list[PageBlocks]:
    first = [text_block(1, first_body, BODY_BASELINE), text_block(1, foot, NOTE_BASELINE)]
    return [PageBlocks(1, first), PageBlocks(2, [text_block(2, NEXT_PAGE_BODY, BODY_BASELINE)])]


class TestUnmarkedNoteTypeBlocksBelowASentenceTheNextPageFinishes(unittest.TestCase):
    def built(self, first_body: str, foot: str) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(FootOfThePagePdf(Path(directory.name) / "foot.pdf", first_body, foot).write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading(first_body, foot)), [], WorkerReadings.none(),
                                 keep_everything())
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_a_note_type_block_below_a_broken_off_sentence_is_a_footnote(self) -> None:
        structure = self.built(BROKEN_OFF_BODY, AUTHORS_NOTE)
        self.assertEqual([AUTHORS_NOTE], [definition.text for definition in structure.definitions()])

    def test_the_broken_off_sentence_runs_on_to_the_next_page_past_the_note(self) -> None:
        structure = self.built(BROKEN_OFF_BODY, AUTHORS_NOTE)
        body = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.assertIn(SENTENCE_RUN_ON, body.split("\n\n"))

    def test_a_note_type_block_below_a_finished_sentence_stays_in_the_body(self) -> None:
        structure = self.built(FINISHED_BODY, AUTHORS_NOTE)
        self.assertEqual([], structure.definitions())

    def test_a_note_type_line_closing_no_sentence_stays_out_of_the_notes(self) -> None:
        structure = self.built(BROKEN_OFF_BODY, RUNNING_FOOT)
        self.assertEqual([], structure.definitions())


if __name__ == "__main__":
    unittest.main()
