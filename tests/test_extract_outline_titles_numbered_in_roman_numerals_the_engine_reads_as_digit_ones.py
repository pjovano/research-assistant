from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
HEADING_SIZE = 10.5
BODY_SIZE = 9.5
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
HEADING_LEFT = 120.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 10.0
CARRIED_BASELINE = 70.0
HEADING_BASELINE = 130.0
OPENING_BASELINE = 170.0
PAGE = 1
MANY_WORDED_TITLE = "II.3 The Need for Permanence"
ONE_WORDED_TITLE = "II.6 Conclusion"
OTHERWISE_NUMBERED_HEADING = "11.7 Conclusion"
CARRIED_SENTENCE = "and so the argument carried over from the page before comes to its end."
OPENING_SENTENCE = "The section opens with a sentence of its own."


class SectionPagePdf:
    def __init__(self, path: Path, title: str) -> None:
        self._path = path
        self._title = title

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, CARRIED_BASELINE), CARRIED_SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            page.insert_text((HEADING_LEFT, HEADING_BASELINE), self._title, fontsize=HEADING_SIZE, fontname=FONT)
            page.insert_text((LEFT, OPENING_BASELINE), OPENING_SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            document.set_toc([[1, self._title, PAGE]])
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(PAGE, kind, html, box, {}, f"/page/{PAGE}/{kind}/{baseline}")


def engine_reading(heading_line: str) -> DocumentBlocks:
    return DocumentBlocks([PageBlocks(PAGE, [
        engine_block(TEXT_KIND, f"<p>{CARRIED_SENTENCE}</p>", CARRIED_BASELINE),
        engine_block(HEADING_KIND, f"<h2>{heading_line}</h2>", HEADING_BASELINE),
        engine_block(TEXT_KIND, f"<p>{OPENING_SENTENCE}</p>", OPENING_BASELINE),
    ])])


class TestOutlineTitlesNumberedInRomanNumeralsTheEngineReadsAsDigitOnes(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def _texts(self, title: str, heading_line: str) -> list[str]:
        pdf_path = SectionPagePdf(Path(self._directory.name) / "section.pdf", title).write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({PAGE}))
        inputs = StructureInputs(engine_reading(heading_line), Outline(pdf_path).headings(),
                                 WorkerReadings.none(), keep_everything())
        elements = NoteStructure(work, inputs).elements()
        return [element.title if isinstance(element, Heading) else element.text for element in elements
                if isinstance(element, (Heading, Paragraph))]

    def test_a_heading_whose_roman_numeral_the_engine_reads_as_digit_ones_opens_the_outline_title_there_once(
            self) -> None:
        texts = self._texts(MANY_WORDED_TITLE, "11.3 The Need for Permanence")
        self.assertEqual([CARRIED_SENTENCE, MANY_WORDED_TITLE, OPENING_SENTENCE], texts)

    def test_a_one_word_heading_whose_roman_numeral_the_engine_reads_as_digit_ones_opens_the_outline_title_there(
            self) -> None:
        texts = self._texts(ONE_WORDED_TITLE, "11.6 Conclusion")
        self.assertEqual([CARRIED_SENTENCE, ONE_WORDED_TITLE, OPENING_SENTENCE], texts)

    def test_a_heading_the_engine_reads_with_the_roman_numeral_opens_the_outline_title_there_once(self) -> None:
        texts = self._texts(MANY_WORDED_TITLE, MANY_WORDED_TITLE)
        self.assertEqual([CARRIED_SENTENCE, MANY_WORDED_TITLE, OPENING_SENTENCE], texts)

    def test_a_heading_numbered_otherwise_than_the_outline_title_opens_below_the_entry_opened_at_its_destination(
            self) -> None:
        texts = self._texts(ONE_WORDED_TITLE, OTHERWISE_NUMBERED_HEADING)
        self.assertEqual([ONE_WORDED_TITLE, CARRIED_SENTENCE, OTHERWISE_NUMBERED_HEADING, OPENING_SENTENCE], texts)


if __name__ == "__main__":
    unittest.main()
