from __future__ import annotations

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
BODY_BASELINE = 100.0
QUOTATION_BASELINE = 440.0
FIRST_NOTE_BASELINE = 500.0
SECOND_NOTE_BASELINE = 520.0
FIRST_PAGE_SENTENCE = "The argument opens with a claim about knowledge."
FIRST_PAGE_NOTE = "A note that runs to the foot of its page."
BODY_SENTENCE = "As the author wrote in a later letter:"
QUOTATION = "Every science begins in the practice it later explains."
SECOND_NOTE = "The letter is dated to the spring."
THIRD_NOTE = "Collected letters, p. 190."


@dataclass(frozen=True)
class MarkedLine:
    baseline: float
    sentence: str
    size: float
    mark: str

    def draw_on(self, page) -> None:
        page.insert_text((LEFT, self.baseline), self.sentence, fontsize=self.size, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(self.sentence, FONT, self.size)
        page.insert_text((mark_left, self.baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)


class QuotationPagesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            self._draw_first_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            self._draw_second_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            document.save(self._path)
        return self._path

    @staticmethod
    def _draw_first_page(page) -> None:
        MarkedLine(BODY_BASELINE, FIRST_PAGE_SENTENCE, BODY_SIZE, "1").draw_on(page)
        page.insert_text((LEFT, FIRST_NOTE_BASELINE), f"1 {FIRST_PAGE_NOTE}", fontsize=NOTE_SIZE, fontname=FONT)

    @staticmethod
    def _draw_second_page(page) -> None:
        MarkedLine(BODY_BASELINE, BODY_SENTENCE, BODY_SIZE, "2").draw_on(page)
        MarkedLine(QUOTATION_BASELINE, QUOTATION, NOTE_SIZE, "3").draw_on(page)
        for baseline, text in [(FIRST_NOTE_BASELINE, f"2 {SECOND_NOTE}"), (SECOND_NOTE_BASELINE, f"3 {THIRD_NOTE}")]:
            page.insert_text((LEFT, baseline), text, fontsize=NOTE_SIZE, fontname=FONT)


@dataclass(frozen=True)
class PageLine:
    file_page: int
    baseline: float


def engine_block(kind: str, html: str, line: PageLine) -> Block:
    box = (LEFT, line.baseline - LINE_HALF_HEIGHT, RIGHT, line.baseline + LINE_HALF_HEIGHT / 2)
    return Block(line.file_page, kind, html, box, {}, f"/page/{line.file_page}/{kind}/{line.baseline}")


def engine_reading() -> list[PageBlocks]:
    first = [engine_block(TEXT_KIND, f"<p>{FIRST_PAGE_SENTENCE}<sup>1</sup></p>", PageLine(1, BODY_BASELINE)),
             engine_block(FOOTNOTE_KIND, f"<p>1 {FIRST_PAGE_NOTE}</p>", PageLine(1, FIRST_NOTE_BASELINE))]
    second = [engine_block(TEXT_KIND, f"<p>{BODY_SENTENCE}<sup>2</sup></p>", PageLine(2, BODY_BASELINE)),
              engine_block(TEXT_KIND, f"<p>{QUOTATION} 3</p>", PageLine(2, QUOTATION_BASELINE)),
              engine_block(FOOTNOTE_KIND, f"<p>2 {SECOND_NOTE}</p>", PageLine(2, FIRST_NOTE_BASELINE)),
              engine_block(FOOTNOTE_KIND, f"<p>3 {THIRD_NOTE}</p>", PageLine(2, SECOND_NOTE_BASELINE))]
    return [PageBlocks(1, first), PageBlocks(2, second)]


class TestNoteTypeQuotationRaisingAMarkTheNotesAnswer(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(QuotationPagesPdf(Path(directory.name) / "pages.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = structure.definitions()

    def test_the_quotation_stays_in_the_body_with_its_mark(self) -> None:
        body = self.text.split("[^1]:")[0]
        self.assertIn(f"{QUOTATION}[^3]", body)

    def test_the_note_open_from_the_page_before_keeps_only_its_own_text(self) -> None:
        self.assertEqual(FIRST_PAGE_NOTE, self.definitions[0].text)

    def test_the_note_the_quotation_marks_takes_the_numeral_the_page_prints(self) -> None:
        self.assertEqual([(1, FIRST_PAGE_NOTE), (2, SECOND_NOTE), (3, THIRD_NOTE)],
                         [(definition.label, definition.text) for definition in self.definitions])


if __name__ == "__main__":
    unittest.main()
