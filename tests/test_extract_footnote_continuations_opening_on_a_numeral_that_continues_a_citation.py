from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINES = (100.0, 140.0)
NOTE_BASELINES = (480.0, 500.0, 520.0)
NOTE_OPENING = "See Siep, Praktische Philosophie, and Williams, New Essays,"
RANGE_CONTINUATION = "47-64. Verweyen, Recht und Sittlichkeit, 5-17."
LISTED_NOTE_OPENING = "Compare the lectures (WLnm, GA iv/3."
LIST_CONTINUATION = "350; FTP 120)."
NEXT_NOTE = "Eigne Meditationen, GA ii/3. 70."
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


@dataclass(frozen=True)
class PrintedLine:
    baseline: float
    text: str
    size: float

    def draw_on(self, page) -> None:
        page.insert_text((LEFT, self.baseline), self.text, fontsize=self.size, fontname=FONT)

    def block(self, file_page: int, kind: str, html: str) -> Block:
        box = (LEFT, self.baseline - LINE_HALF_HEIGHT, RIGHT, self.baseline + LINE_HALF_HEIGHT / 2)
        return Block(file_page, kind, html, box, {}, f"/page/{file_page}/{kind}/{self.baseline}")


@dataclass(frozen=True)
class MarkedSentence:
    line: PrintedLine
    mark: str

    def draw_on(self, page) -> None:
        self.line.draw_on(page)
        mark_left = LEFT + pymupdf.get_text_length(self.line.text, FONT, BODY_SIZE)
        page.insert_text((mark_left, self.line.baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)

    def block(self, file_page: int) -> Block:
        return self.line.block(file_page, TEXT_KIND, f"<p>{self.line.text}<sup>{self.mark}</sup></p>")


@dataclass(frozen=True)
class PrintedNote:
    line: PrintedLine

    def draw_on(self, page) -> None:
        self.line.draw_on(page)

    def block(self, file_page: int) -> Block:
        return self.line.block(file_page, FOOTNOTE_KIND, f"<p>{self.line.text}</p>")


def body(row: int, sentence: str, mark: str) -> MarkedSentence:
    return MarkedSentence(PrintedLine(BODY_BASELINES[row], sentence, BODY_SIZE), mark)


def note(row: int, text: str) -> PrintedNote:
    return PrintedNote(PrintedLine(NOTE_BASELINES[row], text, NOTE_SIZE))


PAGES = {1: [body(0, "Others share parts of this view.", "2"), note(0, f"2 {NOTE_OPENING}")],
         2: [body(0, "The charge is that right rests on coercion.", "3"),
             body(1, "The method is meant for anyone.", "4"),
             note(0, RANGE_CONTINUATION), note(1, f"3 {LISTED_NOTE_OPENING}"),
             note(2, f"{LIST_CONTINUATION} 4 {NEXT_NOTE}")]}


class CitationContinuationsPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            for printed in PAGES.values():
                page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
                for element in printed:
                    element.draw_on(page)
            document.save(self._path)
        return self._path


def engine_reading() -> list[PageBlocks]:
    return [PageBlocks(file_page, [element.block(file_page) for element in printed])
            for file_page, printed in PAGES.items()]


class TestFootnoteContinuationsOpeningOnANumeralThatContinuesACitation(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(CitationContinuationsPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.definitions = DEFINITION_RE.findall(NoteWriter().render(structure.elements(),
                                                                     structure.definitions()).text)

    def test_a_line_opening_on_a_numeral_range_continues_the_note_carried_over(self) -> None:
        self.assertIn(("2", f"{NOTE_OPENING} {RANGE_CONTINUATION}"), self.definitions)

    def test_a_line_opening_on_a_listed_numeral_continues_the_note_above_it(self) -> None:
        self.assertIn(("3", f"{LISTED_NOTE_OPENING} {LIST_CONTINUATION}"), self.definitions)

    def test_the_note_after_a_continued_citation_keeps_only_its_own_text(self) -> None:
        self.assertIn(("4", NEXT_NOTE), self.definitions)

    def test_a_numeral_continuing_a_citation_mints_no_note_of_its_own(self) -> None:
        self.assertEqual(["2", "3", "4"], [label for label, _text in self.definitions])


if __name__ == "__main__":
    unittest.main()
