from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FILE_PAGE = 1
BODY = "The closing sentence of the body."
NOTES_TITLE = "NOTES"
PLAIN_NOTE_LAYER = "1 See D.Henrich, Hegel im Kontext."
PLAIN_NOTE_ENGINE = "1 See D. Henrich, Hegel im Kontext."
NOTATION_NOTE_LAYER = "2 Two points A and C lie apart."
NOTATION_NOTE_ENGINE = "2 Two points <math>A</math> and <math>C</math> lie apart."
NOTATION_NOTE_WRITTEN = "2 Two points $A$ and $C$ lie apart."
SHARED_NOTES_LAYER = ["3 The points B and D meet.", "4 See D.Henrich, again."]
SHARED_NOTES_ENGINE = "3 The points <math>B</math> and <math>D</math> meet. 4 See D. Henrich, again."
BODY_BASELINE = 100.0
TITLE_BASELINE = 300.0
FIRST_NOTE_BASELINE = 330.0
NOTE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0


def baselines(notes: list[str]) -> list[tuple[float, str]]:
    return [(FIRST_NOTE_BASELINE + row * NOTE_PITCH, note) for row, note in enumerate(notes)]


class NotesPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            printed = [(BODY_BASELINE, BODY), (TITLE_BASELINE, NOTES_TITLE)]
            for baseline, text in printed + baselines([PLAIN_NOTE_LAYER, NOTATION_NOTE_LAYER] + SHARED_NOTES_LAYER):
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block(kind: str, text: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, kind, f"<p>{text}</p>", box, {}, f"/page/{FILE_PAGE}/{kind}/{baseline}")


def shared_block() -> Block:
    first, last = baselines([PLAIN_NOTE_ENGINE, NOTATION_NOTE_ENGINE] + SHARED_NOTES_LAYER)[2:]
    box = (LEFT, first[0] - LINE_HALF_HEIGHT, RIGHT, last[0] + LINE_HALF_HEIGHT / 2)
    identifier = f"/page/{FILE_PAGE}/{TEXT_KIND}/shared"
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{SHARED_NOTES_ENGINE}</p>", box, {}, identifier)


def engine_reading() -> list[Block]:
    notes = [engine_block(TEXT_KIND, note, baseline)
             for baseline, note in baselines([PLAIN_NOTE_ENGINE, NOTATION_NOTE_ENGINE])] + [shared_block()]
    opening = [engine_block(TEXT_KIND, BODY, BODY_BASELINE), engine_block(HEADING_KIND, NOTES_TITLE, TITLE_BASELINE)]
    return opening + notes


class TestNotesListsHoldingNotationOnAPageReadFromPixels(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(NotesPagePdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        result = assembler.assemble(PageBlocks(FILE_PAGE, engine_reading()), [], 1)
        self.paragraphs = [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_a_note_the_engine_reads_as_one_block_holding_notation_keeps_its_notation_spans(self) -> None:
        self.assertIn(NOTATION_NOTE_WRITTEN, self.paragraphs)

    def test_a_note_without_notation_keeps_the_text_layers_reading(self) -> None:
        self.assertIn(PLAIN_NOTE_LAYER, self.paragraphs)

    def test_notes_the_engine_reads_as_one_block_together_keep_the_text_layers_reading(self) -> None:
        self.assertEqual(SHARED_NOTES_LAYER, [text for text in self.paragraphs if text in SHARED_NOTES_LAYER])


if __name__ == "__main__":
    unittest.main()
