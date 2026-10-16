from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.strays import StrayFootnotes
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
PAGE_WIDTH = 794.0
PAGE_HEIGHT = 614.0
LEFT_COLUMN = 40.0
RIGHT_COLUMN = 440.0
COLUMN_WIDTH = 320.0
LINE_HALF_HEIGHT = 7.0
CLOSING_WORDS = 2


@dataclass(frozen=True)
class PrintedLine:
    text: str
    kind: str
    left: float
    baseline: float
    size: float

    @property
    def closing_words(self) -> str:
        return " ".join(self.text.split()[-CLOSING_WORDS:])

    def draw_on(self, page) -> None:
        page.insert_text((self.left, self.baseline), self.text, fontsize=self.size, fontname=FONT)

    def block(self) -> Block:
        box = (self.left, self.baseline - LINE_HALF_HEIGHT, self.left + COLUMN_WIDTH,
               self.baseline + LINE_HALF_HEIGHT / 2)
        html = f"<h2>{self.text}</h2>" if self.kind == HEADING_KIND else f"<p>{self.text}</p>"
        return Block(1, self.kind, html, box, {}, f"/page/1/{self.kind}/{self.left}/{self.baseline}")


BODY = PrintedLine("The expansion pursued here is theoretically useful.", TEXT_KIND, LEFT_COLUMN, 80.0, BODY_SIZE)
NOTES_HEADING = PrintedLine("NOTES", HEADING_KIND, LEFT_COLUMN, 250.0, BODY_SIZE)
FIRST_NOTE = PrintedLine("1 This is detailed in a paper in preparation.", FOOTNOTE_KIND, LEFT_COLUMN, 280.0,
                         NOTE_SIZE)
SECOND_NOTE = PrintedLine("2 There are some problems about this theory.", FOOTNOTE_KIND, LEFT_COLUMN, 300.0,
                          NOTE_SIZE)
BIBLIOGRAPHY_HEADING = PrintedLine("BIBLIOGRAPHY", HEADING_KIND, RIGHT_COLUMN, 80.0, BODY_SIZE)
FIRST_ENTRY = PrintedLine("[1] E. Bishop: 1967, Foundations of Constructive Analysis.", TEXT_KIND, RIGHT_COLUMN,
                          110.0, NOTE_SIZE)
CARRIED_ON = PrintedLine("McGuire and J. Bogen, eds., p. 250) Adams claims more.", FOOTNOTE_KIND, RIGHT_COLUMN,
                         80.0, NOTE_SIZE)
THIRD_NOTE = PrintedLine("3 Husserl speaks of logic as formal ontology.", FOOTNOTE_KIND, RIGHT_COLUMN, 280.0,
                         NOTE_SIZE)
ENGINE_ORDER = (BODY, NOTES_HEADING, BIBLIOGRAPHY_HEADING, FIRST_ENTRY, FIRST_NOTE, SECOND_NOTE)
NOTES_IN_BOTH_COLUMNS = (BODY, NOTES_HEADING, FIRST_NOTE, SECOND_NOTE, CARRIED_ON, THIRD_NOTE)
PAGE_ORDER = (BODY, NOTES_HEADING, FIRST_NOTE, SECOND_NOTE, BIBLIOGRAPHY_HEADING, FIRST_ENTRY)


class TwoColumnApparatusPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for line in ENGINE_ORDER:
                line.draw_on(page)
            document.save(self._path)
        return self._path


class TestEndnotesReadAsFootnotesInTheColumnBesideABibliography(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(TwoColumnApparatusPdf(Path(directory.name) / "apparatus.pdf").write())
        self.addCleanup(layer.close)
        blocks = DocumentBlocks([PageBlocks(1, [line.block() for line in ENGINE_ORDER])])
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.body = NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_the_endnotes_stand_beneath_their_heading_before_the_bibliography(self) -> None:
        positions = [self.body.index(line.closing_words) for line in PAGE_ORDER]
        self.assertEqual(sorted(positions), positions)


class TestEndnotesListedInBothColumnsBelowTheirHeading(unittest.TestCase):
    def test_a_note_carried_on_at_the_head_of_the_next_column_keeps_its_place(self) -> None:
        blocks = [line.block() for line in NOTES_IN_BOTH_COLUMNS]
        refiled = StrayFootnotes(blocks, [block.html for block in blocks]).reclassified(blocks)
        self.assertEqual([block.identifier for block in blocks], [block.identifier for block in refiled])


if __name__ == "__main__":
    unittest.main()
