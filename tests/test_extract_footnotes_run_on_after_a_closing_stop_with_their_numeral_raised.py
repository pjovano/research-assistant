from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_SENTENCE, NotedPage, NotedPdf, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FILE_PAGE = 1
FIRST_NOTE = "I am agreeing here with Ginsborg. The question remains why the principle is a heuristic."
SECOND_NOTE = "There is a clear analysis of reproduction according to kind in Kreines."


class TestFootnotesRunOnAfterAClosingStopWithTheirNumeralRaised(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        page = NotedPage(FIRST_SENTENCE, "3", (f"3 {FIRST_NOTE}", f"4 {SECOND_NOTE}"))
        layer = TextLayer(NotedPdf(Path(directory.name) / "notes.pdf", [page]).write())
        self.addCleanup(layer.close)
        reading = PageBlocks(FILE_PAGE, [
            body_block(FILE_PAGE, FIRST_SENTENCE, "<sup>3</sup> and so on<sup>4</sup>"),
            notes_block(FILE_PAGE, FOOTNOTE_KIND, f"<sup>3</sup> {FIRST_NOTE}<sup>4</sup> {SECOND_NOTE}")])
        inputs = StructureInputs(DocumentBlocks([reading]), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({FILE_PAGE}))
        self.structure = NoteStructure(work, inputs)

    def test_the_raised_numeral_after_the_closing_stop_opens_the_next_note(self) -> None:
        self.assertEqual([(3, FIRST_NOTE), (4, SECOND_NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
