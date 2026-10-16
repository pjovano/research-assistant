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

FILE_PAGE = 1
FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
LINE_HALF_HEIGHT = 8.0
RUN_ON_INDENT = 14.0
NOTES_TITLE = "NOTES"
FLUSH, INDENTED = 0.0, RUN_ON_INDENT
CARRIED_LINES = [(INDENTED, "of the argument the page before leaves open, which this line"),
                 (INDENTED, "carries on to its close.")]
NOTE_LINES = [(FLUSH, "10 The next note opens here and runs on past the end of its"),
              (INDENTED, "first line to a second line.")]
CARRIED_TEXT = "of the argument the page before leaves open, which this line carries on to its close."
NOTE_TEXT = "10 The next note opens here and runs on past the end of its first line to a second line."


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class NotesPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        rows = [(FLUSH, NOTES_TITLE)] + CARRIED_LINES + NOTE_LINES
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, (indent, text) in enumerate(rows):
                page.insert_text((LEFT + indent, baseline_of(row)), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def block_over(kind: str, rows: range, text: str) -> Block:
    box = (LEFT, baseline_of(rows.start) - LINE_HALF_HEIGHT, RIGHT, baseline_of(rows.stop - 1) + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, kind, f"<p>{text}</p>", box, {}, f"/page/{FILE_PAGE}/{kind}/{rows.start}")


def engine_reading() -> list[PageBlocks]:
    note_rows = range(1, 1 + len(CARRIED_LINES) + len(NOTE_LINES))
    blocks = [block_over(HEADING_KIND, range(0, 1), NOTES_TITLE),
              block_over(TEXT_KIND, note_rows, f"{CARRIED_TEXT} {NOTE_TEXT}")]
    return [PageBlocks(FILE_PAGE, blocks)]


class TestNotesListsWhoseBlockHoldsOneNumberedNoteBelowCarriedOverLines(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "notes.pdf"

    def paragraphs(self) -> list[str]:
        layer = TextLayer(NotesPagePdf(self._path).write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        return [paragraph.strip() for paragraph in text.strip().split("\n\n")]

    def test_the_numbered_note_opens_a_paragraph_apart_from_the_lines_carried_over_above_it(self) -> None:
        paragraphs = self.paragraphs()
        self.assertEqual([CARRIED_TEXT, NOTE_TEXT], paragraphs[paragraphs.index(f"# {NOTES_TITLE}") + 1:])


if __name__ == "__main__":
    unittest.main()
