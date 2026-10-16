from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from test_extract_note_type_quotations_raising_a_mark_the_notes_answer import (
    BODY_BASELINE, BODY_SIZE, FIRST_NOTE_BASELINE, FIRST_PAGE_NOTE, FIRST_PAGE_SENTENCE, FONT, LEFT, NOTE_SIZE,
    PAGE_HEIGHT, PAGE_WIDTH, QUOTATION_BASELINE, SECOND_NOTE, MarkedLine, PageLine, engine_block,
)
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

HEADING_BASELINE = 400.0
BODY_SENTENCE = "The second part draws the consequences for the theory."
HEADING = "Sources"
ENTRIES = "Anscombe, G. E. M.: An Introduction to the Tractatus, 1959."


class HeadedEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            MarkedLine(BODY_BASELINE, FIRST_PAGE_SENTENCE, BODY_SIZE, "1").draw_on(first)
            first.insert_text((LEFT, FIRST_NOTE_BASELINE), f"1 {FIRST_PAGE_NOTE}", fontsize=NOTE_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            MarkedLine(BODY_BASELINE, BODY_SENTENCE, BODY_SIZE, "2").draw_on(second)
            second.insert_text((LEFT, HEADING_BASELINE), HEADING, fontsize=BODY_SIZE, fontname=FONT)
            second.insert_text((LEFT, QUOTATION_BASELINE), ENTRIES, fontsize=NOTE_SIZE, fontname=FONT)
            second.insert_text((LEFT, FIRST_NOTE_BASELINE), f"2 {SECOND_NOTE}", fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_reading() -> list[PageBlocks]:
    first = [engine_block(TEXT_KIND, f"<p>{FIRST_PAGE_SENTENCE}<sup>1</sup></p>", PageLine(1, BODY_BASELINE)),
             engine_block(FOOTNOTE_KIND, f"<p>1 {FIRST_PAGE_NOTE}</p>", PageLine(1, FIRST_NOTE_BASELINE))]
    second = [engine_block(TEXT_KIND, f"<p>{BODY_SENTENCE}<sup>2</sup></p>", PageLine(2, BODY_BASELINE)),
              engine_block(HEADING_KIND, f"<h2>{HEADING}</h2>", PageLine(2, HEADING_BASELINE)),
              engine_block(TEXT_KIND, f"<p>{ENTRIES}</p>", PageLine(2, QUOTATION_BASELINE)),
              engine_block(FOOTNOTE_KIND, f"<p>2 {SECOND_NOTE}</p>", PageLine(2, FIRST_NOTE_BASELINE))]
    return [PageBlocks(1, first), PageBlocks(2, second)]


class TestNoteTypeBlocksOpeningTheSectionOfAHeadingAboveThem(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(HeadedEntriesPdf(Path(directory.name) / "pages.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = structure.definitions()

    def test_the_block_stays_in_the_body_below_its_heading(self) -> None:
        body = self.text.split("[^1]:")[0]
        self.assertIn(ENTRIES, body)

    def test_the_note_open_from_the_page_before_keeps_only_its_own_text(self) -> None:
        self.assertEqual([(1, FIRST_PAGE_NOTE), (2, SECOND_NOTE)],
                         [(definition.label, definition.text) for definition in self.definitions])


if __name__ == "__main__":
    unittest.main()
