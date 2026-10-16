from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_NOTE_BASELINE, FIRST_SENTENCE, LEFT, LINE_HALF_HEIGHT, RIGHT, SECOND_NOTE_BASELINE, NotedPage, NotedPdf,
    body_block,
)
from _extract.blocks import FOOTNOTE_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FILE_PAGE = 1
UPPER_NUMERAL = "9"
LOWER_NUMERAL = "10"
UPPER_NOTE = "Formally, the principle of contraposition holds."
LOWER_NOTE = "Formally, the principle of double negation holds."
NARROWER_BY = 200.0
UPPER_BOX = (LEFT, FIRST_NOTE_BASELINE - LINE_HALF_HEIGHT, RIGHT, FIRST_NOTE_BASELINE + LINE_HALF_HEIGHT / 2)
LOWER_BOX_REACHING_OVER_THE_UPPER_LINE = (LEFT, FIRST_NOTE_BASELINE - LINE_HALF_HEIGHT, RIGHT - NARROWER_BY,
                                          SECOND_NOTE_BASELINE + LINE_HALF_HEIGHT / 2)


def note_block(box: tuple, numeral: str, note: str) -> Block:
    return Block(FILE_PAGE, FOOTNOTE_KIND, f"<p><sup>{numeral}</sup> {note}</p>", box, {},
                 f"/page/{FILE_PAGE}/Footnote/{numeral}")


class TestFootnotesOpeningOnTheWordsOfTheNoteAboveInABlockReachingOverIt(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        page = NotedPage(FIRST_SENTENCE, UPPER_NUMERAL,
                         (f"{UPPER_NUMERAL} {UPPER_NOTE}", f"{LOWER_NUMERAL} {LOWER_NOTE}"))
        layer = TextLayer(NotedPdf(Path(directory.name) / "notes.pdf", [page]).write())
        self.addCleanup(layer.close)
        marks = f"<sup>{UPPER_NUMERAL}</sup> and<sup>{LOWER_NUMERAL}</sup>"
        reading = PageBlocks(FILE_PAGE, [body_block(FILE_PAGE, FIRST_SENTENCE, marks),
                                         note_block(UPPER_BOX, UPPER_NUMERAL, UPPER_NOTE),
                                         note_block(LOWER_BOX_REACHING_OVER_THE_UPPER_LINE, LOWER_NUMERAL, LOWER_NOTE)])
        inputs = StructureInputs(DocumentBlocks([reading]), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({FILE_PAGE}))
        self.structure = NoteStructure(work, inputs)

    def test_each_note_keeps_the_numeral_the_layer_prints_before_its_words(self) -> None:
        self.assertEqual([(int(UPPER_NUMERAL), UPPER_NOTE), (int(LOWER_NUMERAL), LOWER_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
