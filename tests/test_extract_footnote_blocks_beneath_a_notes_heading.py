from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY = "The closing sentence of the body."
NOTES_TITLE = "NOTES"
NOTES = ["1 The first endnote.", "2 The second endnote."]
BODY_BASELINE = 100.0
TITLE_BASELINE = 300.0
FIRST_NOTE_BASELINE = 330.0
NOTE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0


class NotesPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text in [(BODY_BASELINE, BODY), (TITLE_BASELINE, NOTES_TITLE)] + note_lines():
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def note_lines() -> list[tuple[float, str]]:
    return [(FIRST_NOTE_BASELINE + row * NOTE_PITCH, note) for row, note in enumerate(NOTES)]


def engine_block(kind: str, text: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, f"<p>{text}</p>", box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading() -> list[Block]:
    notes = [engine_block(FOOTNOTE_KIND, note, baseline) for baseline, note in note_lines()]
    return [engine_block(TEXT_KIND, BODY, BODY_BASELINE),
            engine_block(HEADING_KIND, NOTES_TITLE, TITLE_BASELINE)] + notes


class TestFootnoteBlocksBeneathANotesHeading(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(NotesPagePdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        self.result = assembler.assemble(PageBlocks(1, engine_reading()), [], 1)

    def test_a_block_the_engine_reads_as_a_footnote_beneath_a_notes_heading_defines_no_footnote(self) -> None:
        self.assertEqual([], self.result.definitions)

    def test_a_block_the_engine_reads_as_a_footnote_beneath_a_notes_heading_stays_an_entry_of_the_list(
            self) -> None:
        paragraphs = [element.text for element in self.result.elements if isinstance(element, Paragraph)]
        self.assertEqual([BODY] + NOTES, paragraphs)


if __name__ == "__main__":
    unittest.main()
