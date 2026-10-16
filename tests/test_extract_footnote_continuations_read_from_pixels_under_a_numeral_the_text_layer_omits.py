from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_NOTE_BASELINE, FIRST_SENTENCE, NOTE_CONTINUATION, NOTE_OPENING, SECOND_NOTE, SECOND_NOTE_BASELINE,
    SECOND_SENTENCE, EngineRegion, NotedPage, NotedPdf, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

PIXEL_PAGES = frozenset({1, 2})
NUMERAL_READ_ON_THE_CONTINUATION = "2"
NUMERAL_READ_ON_THE_SECOND_NOTE = "3"


class TestFootnoteContinuationsReadFromPixelsUnderANumeralTheTextLayerOmits(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        pages = [NotedPage(FIRST_SENTENCE, "1", (f"1 {NOTE_OPENING}",)),
                 NotedPage(SECOND_SENTENCE, "2", (NOTE_CONTINUATION, f"2 {SECOND_NOTE}"))]
        layer = TextLayer(NotedPdf(Path(directory.name) / "notes.pdf", pages).write())
        self.addCleanup(layer.close)
        continuation = f"<p><sup>{NUMERAL_READ_ON_THE_CONTINUATION}</sup> {NOTE_CONTINUATION}</p>"
        second_note = f"<p><sup>{NUMERAL_READ_ON_THE_SECOND_NOTE}</sup> {SECOND_NOTE}</p>"
        reading = [
            PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>1</sup>"),
                           notes_block(1, FOOTNOTE_KIND, f"<sup>1</sup> {NOTE_OPENING}")]),
            PageBlocks(2, [body_block(2, SECOND_SENTENCE, "<sup>2</sup>"),
                           EngineRegion(FIRST_NOTE_BASELINE, FIRST_NOTE_BASELINE).block(2, FOOTNOTE_KIND, continuation),
                           EngineRegion(SECOND_NOTE_BASELINE, SECOND_NOTE_BASELINE).block(2, FOOTNOTE_KIND,
                                                                                          second_note)]),
        ]
        inputs = StructureInputs(DocumentBlocks(reading), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=PIXEL_PAGES)
        self.structure = NoteStructure(work, inputs)

    def test_the_continuation_finishes_the_note_the_page_before_leaves_open(self) -> None:
        self.assertEqual((1, f"{NOTE_OPENING} {NOTE_CONTINUATION}"),
                         (self.structure.definitions()[0].label, self.structure.definitions()[0].text))

    def test_the_next_note_keeps_the_numeral_the_text_layer_prints(self) -> None:
        self.assertEqual([(2, SECOND_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()[1:]])


if __name__ == "__main__":
    unittest.main()
