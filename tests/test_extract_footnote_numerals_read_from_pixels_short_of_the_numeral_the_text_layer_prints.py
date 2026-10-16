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
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FILE_PAGE = 1
PRINTED_NUMERAL = "31"
READ_NUMERAL = "1"
NOTE = "It is open opportunity for a subvaluationist evaluation."
LINE_OPENING_ON_ANOTHER_NUMERAL = "727f. of the lectures."


class PixelPageCase(unittest.TestCase):
    def built(self, printed_lines: tuple[str, ...], mark: str, read_note: str) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        page = NotedPage(FIRST_SENTENCE, mark, printed_lines)
        layer = TextLayer(NotedPdf(Path(directory.name) / "notes.pdf", [page]).write())
        self.addCleanup(layer.close)
        reading = PageBlocks(FILE_PAGE, [body_block(FILE_PAGE, FIRST_SENTENCE, f"<sup>{mark}</sup>"),
                                         notes_block(FILE_PAGE, FOOTNOTE_KIND, read_note)])
        inputs = StructureInputs(DocumentBlocks([reading]), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({FILE_PAGE}))
        return NoteStructure(work, inputs)


class TestFootnoteNumeralsReadFromPixelsShortOfTheNumeralTheTextLayerPrints(PixelPageCase):
    def setUp(self) -> None:
        self.structure = self.built((f"{PRINTED_NUMERAL} {NOTE}",), PRINTED_NUMERAL,
                                    f"<sup>{READ_NUMERAL}</sup> {NOTE}")

    def test_the_note_takes_the_numeral_the_text_layer_prints(self) -> None:
        self.assertEqual([(int(PRINTED_NUMERAL), NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])

    def test_the_mark_links_to_the_note(self) -> None:
        paragraphs = [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]
        self.assertEqual([f"{FIRST_SENTENCE}[^{PRINTED_NUMERAL}]"], paragraphs)


class TestANumeralOpeningAnotherLineOfTheNotesBlock(PixelPageCase):
    def test_the_note_keeps_the_numeral_the_layer_prints_before_its_own_words(self) -> None:
        structure = self.built((LINE_OPENING_ON_ANOTHER_NUMERAL, f"{READ_NUMERAL} {NOTE}"), READ_NUMERAL,
                               f"<sup>{READ_NUMERAL}</sup> {NOTE}")
        self.assertEqual([int(READ_NUMERAL)], [definition.label for definition in structure.definitions()])


if __name__ == "__main__":
    unittest.main()
