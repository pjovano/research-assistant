from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
TITLE_SIZE = 12.0
BODY_SIZE = 10.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 10.0
TITLE_BASELINE = 90.0
BODY_BASELINE = 140.0
PAGE = 1
SECTION_TITLE = "1.1 Intentional History"
ROMAN_READING = "I.I Intentional History"
OTHER_ROMAN_READING = "I.II Intentional History"
SENTENCE = "The section opens with a sentence of its own."


class SectionPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, TITLE_BASELINE), SECTION_TITLE, fontsize=TITLE_SIZE, fontname=FONT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            document.set_toc([[1, SECTION_TITLE, PAGE]])
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(PAGE, kind, html, box, {}, f"/page/{PAGE}/{kind}/{baseline}")


def pixel_reading(heading_text: str) -> DocumentBlocks:
    return DocumentBlocks([PageBlocks(PAGE, [engine_block(HEADING_KIND, f"<h3>{heading_text}</h3>", TITLE_BASELINE),
                                             engine_block(TEXT_KIND, f"<p>{SENTENCE}</p>", BODY_BASELINE)])])


class TestDottedSectionNumbersReadInRomanNumerals(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._pdf_path = SectionPagePdf(Path(directory.name) / "section.pdf").write()
        self._layer = TextLayer(self._pdf_path)
        self.addCleanup(self._layer.close)

    def _heading_titles(self, heading_text: str) -> list[str]:
        work = WorkInputs(self._layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({PAGE}))
        inputs = StructureInputs(pixel_reading(heading_text), Outline(self._pdf_path).headings(),
                                 WorkerReadings.none(), keep_everything())
        return [element.title for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_a_heading_read_with_the_outline_entrys_number_in_roman_numerals_is_written_once(self) -> None:
        self.assertEqual([SECTION_TITLE], self._heading_titles(ROMAN_READING))

    def test_a_heading_read_with_another_number_in_roman_numerals_stays_its_own_heading(self) -> None:
        self.assertCountEqual([SECTION_TITLE, OTHER_ROMAN_READING], self._heading_titles(OTHER_ROMAN_READING))


if __name__ == "__main__":
    unittest.main()
