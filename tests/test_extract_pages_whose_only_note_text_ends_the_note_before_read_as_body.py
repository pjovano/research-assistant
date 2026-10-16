from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from test_extract_note_type_quotations_raising_a_mark_the_notes_answer import (
    BODY_BASELINE, BODY_SIZE, FIRST_NOTE_BASELINE, FIRST_PAGE_SENTENCE, FONT, LEFT, NOTE_SIZE, PAGE_HEIGHT, PAGE_WIDTH,
    MarkedLine, PageLine, engine_block,
)
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

UNFINISHED_NOTE = "Moreau objects that the text suggests on this basis"
FINISHED_NOTE = "Moreau objects to this reading."
CLOSING_WORDS = "that the essences of things are eternal truths."
BODY_SENTENCE = "The second page carries on the argument."


class CarriedFootPdf:
    def __init__(self, path: Path, first_note: str) -> None:
        self._path = path
        self._first_note = first_note

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            MarkedLine(BODY_BASELINE, FIRST_PAGE_SENTENCE, BODY_SIZE, "1").draw_on(first)
            first.insert_text((LEFT, FIRST_NOTE_BASELINE), f"1 {self._first_note}", fontsize=NOTE_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((LEFT, BODY_BASELINE), BODY_SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            second.insert_text((LEFT, FIRST_NOTE_BASELINE), CLOSING_WORDS, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestPagesWhoseOnlyNoteTextIsTheEndOfTheNoteBeforeReadAsBody(unittest.TestCase):
    def built(self, first_note: str) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(CarriedFootPdf(Path(directory.name) / "pages.pdf", first_note).write())
        self.addCleanup(layer.close)
        pages = [PageBlocks(1, [engine_block(TEXT_KIND, f"<p>{FIRST_PAGE_SENTENCE}<sup>1</sup></p>",
                                             PageLine(1, BODY_BASELINE)),
                                engine_block(FOOTNOTE_KIND, f"<p>1 {first_note}</p>",
                                             PageLine(1, FIRST_NOTE_BASELINE))]),
                 PageBlocks(2, [engine_block(TEXT_KIND, f"<p>{BODY_SENTENCE}</p>", PageLine(2, BODY_BASELINE)),
                                engine_block(TEXT_KIND, f"<p>{CLOSING_WORDS}</p>", PageLine(2, FIRST_NOTE_BASELINE))])]
        inputs = StructureInputs(DocumentBlocks(pages), [], WorkerReadings.none(), keep_everything())
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_the_foot_of_the_page_ends_the_note_the_page_before_leaves_unfinished(self) -> None:
        structure = self.built(UNFINISHED_NOTE)
        self.assertEqual([(1, f"{UNFINISHED_NOTE} {CLOSING_WORDS}")],
                         [(definition.label, definition.text) for definition in structure.definitions()])

    def test_the_foot_of_the_page_stays_in_the_body_after_a_note_that_ends_its_sentence(self) -> None:
        structure = self.built(FINISHED_NOTE)
        paragraphs = [element.text for element in structure.elements() if isinstance(element, Paragraph)]
        self.assertIn(CLOSING_WORDS, paragraphs)


if __name__ == "__main__":
    unittest.main()
