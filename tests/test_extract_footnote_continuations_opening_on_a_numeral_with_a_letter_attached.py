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
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 500.0
MARK = "1"
FIRST_BODY = "The dialogue closes on a reinstatement of convention."
SECOND_BODY = "Hermogenes opens the discussion with his own view."
NOTE_OPENING = "The crucial passage is Socrates' conclusion at"
CONTINUATION = "435c-d; the principal support is found at 434c-5a."
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


class PrintedLine(NamedTuple):
    file_page: int
    baseline: float
    text: str

    def block(self, kind: str, html: str) -> Block:
        box = (LEFT, self.baseline - LINE_HALF_HEIGHT, RIGHT, self.baseline + LINE_HALF_HEIGHT / 2)
        return Block(self.file_page, kind, html, box, {}, f"/page/{self.file_page}/{kind}/{self.baseline}")


FIRST_PAGE_BODY = PrintedLine(1, BODY_BASELINE, FIRST_BODY)
FIRST_PAGE_NOTE = PrintedLine(1, NOTE_BASELINE, f"{MARK} {NOTE_OPENING}")
SECOND_PAGE_BODY = PrintedLine(2, BODY_BASELINE, SECOND_BODY)
SECOND_PAGE_NOTE = PrintedLine(2, NOTE_BASELINE, CONTINUATION)


def written_pdf(path: Path) -> Path:
    with pymupdf.open() as document:
        for lines in ((FIRST_PAGE_BODY, FIRST_PAGE_NOTE), (SECOND_PAGE_BODY, SECOND_PAGE_NOTE)):
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for line in lines:
                size = BODY_SIZE if line.baseline == BODY_BASELINE else NOTE_SIZE
                page.insert_text((LEFT, line.baseline), line.text, fontsize=size, fontname=FONT)
        document.save(path)
    return path


def engine_reading() -> list[PageBlocks]:
    first = [FIRST_PAGE_BODY.block(TEXT_KIND, f"<p>{FIRST_BODY}<sup>{MARK}</sup></p>"),
             FIRST_PAGE_NOTE.block(FOOTNOTE_KIND, f"<p><sup>{MARK}</sup> {NOTE_OPENING}</p>")]
    second = [SECOND_PAGE_BODY.block(TEXT_KIND, f"<p>{SECOND_BODY}</p>"),
              SECOND_PAGE_NOTE.block(FOOTNOTE_KIND, f"<hr/><p>{CONTINUATION}</p>")]
    return [PageBlocks(1, first), PageBlocks(2, second)]


class TestFootnoteContinuationsOpeningOnANumeralWithALetterAttached(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(written_pdf(Path(directory.name) / "notes.pdf"))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({1, 2}))
        structure = NoteStructure(work, inputs)
        self.definitions = DEFINITION_RE.findall(NoteWriter().render(structure.elements(),
                                                                     structure.definitions()).text)

    def test_the_continuation_runs_on_the_note_carried_over(self) -> None:
        self.assertIn((MARK, f"{NOTE_OPENING} {CONTINUATION}"), self.definitions)

    def test_the_numeral_with_a_letter_attached_mints_no_note_of_its_own(self) -> None:
        self.assertEqual([MARK], [label for label, _text in self.definitions])


if __name__ == "__main__":
    unittest.main()
