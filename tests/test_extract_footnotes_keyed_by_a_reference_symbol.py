from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

BUILTIN_FONT = "tiro"
EMBEDDED_FONT = "F0"
FILE_PAGE = 1
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
DAGGER = "†"
STAR = "*"
SENTENCE = "The theme of phenomenology is intentionality."
STAR_NOTE = "To be presented at a symposium in December."
DAGGER_NOTE = "The first book, page 203, of the standard edition."


class PrintedLine(NamedTuple):
    baseline: float
    text: str
    size: float

    def block(self, kind: str, html: str) -> Block:
        box = (LEFT, self.baseline - LINE_HALF_HEIGHT, RIGHT, self.baseline + LINE_HALF_HEIGHT / 2)
        return Block(FILE_PAGE, kind, html, box, {}, f"/page/{FILE_PAGE}/{kind}/{self.baseline}")


BODY = PrintedLine(100.0, SENTENCE, BODY_SIZE)
FIRST_NOTE = PrintedLine(500.0, f"{STAR} {STAR_NOTE}", NOTE_SIZE)
SECOND_NOTE = PrintedLine(520.0, f"{DAGGER} {DAGGER_NOTE}", NOTE_SIZE)


def written_pdf(path: Path, body_mark: str) -> Path:
    font = pymupdf.Font(BUILTIN_FONT)
    with pymupdf.open() as document:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_font(fontname=EMBEDDED_FONT, fontbuffer=font.buffer)
        page.insert_text((LEFT, BODY.baseline), BODY.text, fontsize=BODY.size, fontname=EMBEDDED_FONT)
        mark_place = (LEFT + font.text_length(SENTENCE, fontsize=BODY_SIZE), BODY.baseline - MARK_RISE)
        page.insert_text(mark_place, body_mark, fontsize=MARK_SIZE, fontname=EMBEDDED_FONT)
        for line in (FIRST_NOTE, SECOND_NOTE):
            page.insert_text((LEFT, line.baseline), line.text, fontsize=line.size, fontname=EMBEDDED_FONT)
        document.save(path)
    return path


def engine_reading(body_mark: str) -> list[PageBlocks]:
    raised = f"<sup>{body_mark}</sup>" if body_mark else ""
    return [PageBlocks(FILE_PAGE, [BODY.block(TEXT_KIND, f"<p>{SENTENCE}{raised}</p>"),
                                   FIRST_NOTE.block(FOOTNOTE_KIND, f"<p>{STAR} {STAR_NOTE}</p>"),
                                   SECOND_NOTE.block(FOOTNOTE_KIND, f"<p><sup>{DAGGER}</sup> {DAGGER_NOTE}</p>")])]


class TestFootnotesKeyedByAReferenceSymbol(unittest.TestCase):
    def built(self, body_mark: str) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(written_pdf(Path(directory.name) / "symbols.pdf", body_mark))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading(body_mark)), [], WorkerReadings.none(),
                                 keep_everything())
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_a_raised_symbol_links_the_note_opening_on_that_symbol(self) -> None:
        structure = self.built(DAGGER)
        paragraphs = [element.text for element in structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual([f"{SENTENCE}[^1]"], paragraphs)

    def test_the_marked_symbol_note_drops_its_symbol(self) -> None:
        definitions = self.built(DAGGER).definitions()
        self.assertIn((1, DAGGER_NOTE), [(definition.label, definition.text) for definition in definitions])

    def test_a_note_opening_on_another_symbol_stays_a_note_of_its_own(self) -> None:
        definitions = self.built(DAGGER).definitions()
        self.assertIn(f"{STAR} {STAR_NOTE}", [definition.text for definition in definitions])

    def test_an_unmarked_symbol_note_keeps_its_symbol_without_a_full_stop(self) -> None:
        definitions = self.built("").definitions()
        self.assertIn(f"{DAGGER} {DAGGER_NOTE}", [definition.text for definition in definitions])


if __name__ == "__main__":
    unittest.main()
