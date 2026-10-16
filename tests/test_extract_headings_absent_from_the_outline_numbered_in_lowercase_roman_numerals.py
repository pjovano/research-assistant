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
SECTION_SIZE = 12.0
SUBSECTION_SIZE = 10.5
BODY_SIZE = 9.5
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
SUBSECTION_LEFT = 70.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 10.0
SECTION_BASELINE = 90.0
FIRST_BODY_BASELINE = 130.0
SUBSECTION_BASELINE = 180.0
SECOND_BODY_BASELINE = 220.0
PAGE = 1
SECTION_TITLE = "3. Analytic versus Synthetic"
NUMBERED_SUBSECTION = "ii. The Three Definitions"
LOWERCASE_FRAGMENT = "and the reading closes there"
FIRST_SENTENCE = "The section opens with a sentence of its own."
SECOND_SENTENCE = "The subsection carries on with another sentence."


class SubsectionPagePdf:
    def __init__(self, path: Path, subsection_line: str) -> None:
        self._path = path
        self._subsection_line = subsection_line

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, SECTION_BASELINE), SECTION_TITLE, fontsize=SECTION_SIZE, fontname=FONT)
            page.insert_text((LEFT, FIRST_BODY_BASELINE), FIRST_SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            page.insert_text((SUBSECTION_LEFT, SUBSECTION_BASELINE), self._subsection_line,
                             fontsize=SUBSECTION_SIZE, fontname=FONT)
            page.insert_text((LEFT, SECOND_BODY_BASELINE), SECOND_SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            document.set_toc([[1, SECTION_TITLE, PAGE]])
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(PAGE, kind, html, box, {}, f"/page/{PAGE}/{kind}/{baseline}")


def engine_reading(subsection_line: str) -> DocumentBlocks:
    return DocumentBlocks([PageBlocks(PAGE, [
        engine_block(HEADING_KIND, f"<h1>{SECTION_TITLE}</h1>", SECTION_BASELINE),
        engine_block(TEXT_KIND, f"<p>{FIRST_SENTENCE}</p>", FIRST_BODY_BASELINE),
        engine_block(HEADING_KIND, f"<h2>{subsection_line}</h2>", SUBSECTION_BASELINE),
        engine_block(TEXT_KIND, f"<p>{SECOND_SENTENCE}</p>", SECOND_BODY_BASELINE),
    ])])


class TestHeadingsAbsentFromTheOutlineNumberedInLowercaseRomanNumerals(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def _heading_titles(self, subsection_line: str) -> list[str]:
        pdf_path = SubsectionPagePdf(Path(self._directory.name) / "subsection.pdf", subsection_line).write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts())
        inputs = StructureInputs(engine_reading(subsection_line), Outline(pdf_path).headings(),
                                 WorkerReadings.none(), keep_everything())
        return [element.title for element in NoteStructure(work, inputs).elements() if isinstance(element, Heading)]

    def test_a_heading_opening_on_a_lowercase_roman_section_number_opens_beneath_the_outline_entry(self) -> None:
        self.assertEqual([SECTION_TITLE, NUMBERED_SUBSECTION], self._heading_titles(NUMBERED_SUBSECTION))

    def test_a_heading_block_opening_lowercase_without_a_section_number_opens_no_heading(self) -> None:
        self.assertEqual([SECTION_TITLE], self._heading_titles(LOWERCASE_FRAGMENT))


if __name__ == "__main__":
    unittest.main()
