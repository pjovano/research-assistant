from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

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
FILE_PAGE = 1
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
NUMBERED_SENTENCE = "The chapters that follow treat the rules of the syllogism."
LETTERED_SENTENCE = "They have little practical use."
NUMBERED_MARK = "1"
LETTER = "a"
NUMBERED_NOTE = "Prior Analytics, book one, chapters four to seven."
LETTERED_NOTE = "... use, if only for exercising the mind."
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


class PrintedLine(NamedTuple):
    baseline: float
    text: str
    size: float

    def block(self, kind: str, html: str) -> Block:
        box = (LEFT, self.baseline - LINE_HALF_HEIGHT, RIGHT, self.baseline + LINE_HALF_HEIGHT / 2)
        return Block(FILE_PAGE, kind, html, box, {}, f"/page/{FILE_PAGE}/{kind}/{self.baseline}")


BODY = PrintedLine(100.0, f"{NUMBERED_SENTENCE} {LETTERED_SENTENCE}", BODY_SIZE)
FIRST_NOTE = PrintedLine(500.0, f"{NUMBERED_MARK} {NUMBERED_NOTE}", NOTE_SIZE)
SECOND_NOTE = PrintedLine(520.0, f"{LETTER} {LETTERED_NOTE}", NOTE_SIZE)


def written_pdf(path: Path) -> Path:
    with pymupdf.open() as document:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        for line in (BODY, FIRST_NOTE, SECOND_NOTE):
            page.insert_text((LEFT, line.baseline), line.text, fontsize=line.size, fontname=FONT)
        document.save(path)
    return path


def engine_reading() -> list[PageBlocks]:
    body_html = f"<p>{NUMBERED_SENTENCE}<sup>{NUMBERED_MARK}</sup> {LETTERED_SENTENCE}<sup>{LETTER}</sup></p>"
    return [PageBlocks(FILE_PAGE, [BODY.block(TEXT_KIND, body_html),
                                   FIRST_NOTE.block(FOOTNOTE_KIND, f"<p><sup>{NUMBERED_MARK}</sup> {NUMBERED_NOTE}</p>"),
                                   SECOND_NOTE.block(FOOTNOTE_KIND, f"<p><sup>{LETTER}</sup> {LETTERED_NOTE}</p>")])]


class TestFootnotesKeyedByARaisedLetter(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(written_pdf(Path(directory.name) / "lettered.pdf"))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({FILE_PAGE}))
        structure = NoteStructure(work, inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = dict((text, label) for label, text in DEFINITION_RE.findall(self.text))

    def test_the_numbered_note_keeps_only_its_own_text(self) -> None:
        self.assertIn(NUMBERED_NOTE, self.definitions)

    def test_the_lettered_note_is_a_note_of_its_own(self) -> None:
        self.assertIn(LETTERED_NOTE, self.definitions)

    def test_the_raised_letter_in_the_body_references_the_lettered_note(self) -> None:
        self.assertIn(f"{LETTERED_SENTENCE}[^{self.definitions.get(LETTERED_NOTE)}]", self.text)


if __name__ == "__main__":
    unittest.main()
