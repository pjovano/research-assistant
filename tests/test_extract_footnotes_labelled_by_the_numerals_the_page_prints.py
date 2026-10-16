from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, excluding
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.spans import PagePlace
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
BODY_BASELINES = (100.0, 140.0, 180.0)
NOTE_BASELINES = (480.0, 500.0, 520.0)
EXCLUDED_NOTE_TOP = NOTE_BASELINES[2] - LINE_HALF_HEIGHT
EXCLUDED_NOTE_BOTTOM = NOTE_BASELINES[2] + LINE_HALF_HEIGHT / 2
UNNUMBERED_NOTE = "Read at a meeting of the society."
FIRST_NOTE = "Mach, Popular Lectures, p. 4."
THANKS_NOTE = "I thank my colleagues for their help."
FOURTH_NOTE = "James, Collected Essays, p. 449."
FIFTH_NOTE = "Thiele, Correspondence, p. 168."
DEFINITION_LABEL_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)
MARK_LABEL_RE = re.compile(r"\[\^(\d+)\](?!:)")


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


FIRST_PAGE = [body(0, "The lectures reached a wide public.", "1"),
              body(1, "They were given in Vienna and Prague.", "2"),
              note(0, UNNUMBERED_NOTE), note(1, f"1 {FIRST_NOTE}"), note(2, f"2 {THANKS_NOTE}")]
SECOND_PAGE = [body(0, "James visited Mach in Prague.", "3"),
               body(1, "He wrote of the visit to his wife.", "4"),
               body(2, "Mach later dedicated a book to him.", "5"),
               note(0, f"4 {FOURTH_NOTE}"), note(1, f"5 {FIFTH_NOTE}")]
PAGES = {1: FIRST_PAGE, 2: SECOND_PAGE}


class NumberedFootnotesPdf:
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


class TestFootnotesLabelledByTheNumeralsThePagePrints(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(NumberedFootnotesPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        thanks_note = excluding(PagePlace(1, EXCLUDED_NOTE_TOP), PagePlace(1, EXCLUDED_NOTE_BOTTOM))
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), thanks_note)
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_a_note_after_an_excluded_note_keeps_its_printed_numeral(self) -> None:
        self.assertIn(("4", FOURTH_NOTE), DEFINITION_LABEL_RE.findall(self.text))

    def test_a_note_after_a_mark_with_no_definition_keeps_its_printed_numeral(self) -> None:
        self.assertIn(("5", FIFTH_NOTE), DEFINITION_LABEL_RE.findall(self.text))

    def test_an_unnumbered_note_beside_the_first_does_not_shift_its_numeral(self) -> None:
        self.assertIn(("1", FIRST_NOTE), DEFINITION_LABEL_RE.findall(self.text))

    def test_the_marks_in_the_body_carry_the_printed_numerals(self) -> None:
        self.assertEqual(["1", "4", "5"], MARK_LABEL_RE.findall(self.text))

    def test_an_unnumbered_note_takes_a_label_above_every_printed_numeral(self) -> None:
        self.assertIn(("6", UNNUMBERED_NOTE), DEFINITION_LABEL_RE.findall(self.text))

    def test_every_definition_label_is_unique(self) -> None:
        labels = [label for label, _text in DEFINITION_LABEL_RE.findall(self.text)]
        self.assertEqual(len(set(labels)), len(labels))


if __name__ == "__main__":
    unittest.main()
