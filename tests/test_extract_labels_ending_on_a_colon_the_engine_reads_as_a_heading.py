from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading

LEAD_IN = "In connection with it, I should like to propose the following thesis:"
LABEL = "THESIS OF THE UNIVERSAL SHARING OF LABOR:"
QUOTATION = "Every community shares out the labor of fixing what its words refer to."
SUBLEVEL = 2
FILE_PAGE = 1
BODY_FONT = "helv"
LABEL_FONT = "tiro"
LEFT = 72.0
QUOTATION_INDENT = 12.0
RIGHT = 540.0
BODY_SIZE = 10.0
LABEL_SIZE = 7.0
ROW_PITCH = 30.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 12.0
ROWS = [(TEXT_KIND, LEAD_IN, BODY_FONT, BODY_SIZE, LEFT),
        (HEADING_KIND, LABEL, LABEL_FONT, LABEL_SIZE, LEFT + QUOTATION_INDENT),
        (TEXT_KIND, QUOTATION, BODY_FONT, BODY_SIZE, LEFT + QUOTATION_INDENT)]


class LabelledQuotationPage:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "labelled.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, (_kind, text, font, size, left) in enumerate(ROWS):
                page.insert_text((left, _baseline(index)), text, fontsize=size, fontname=font)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, kind, f"<p>{text}</p>", _box(index, left), {},
                                            f"/page/1/{index}")
                                      for index, (kind, text, _font, _size, left) in enumerate(ROWS)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int, left: float) -> tuple:
    baseline = _baseline(index)
    return (left - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestLabelsEndingOnAColonTheEngineReadsAsAHeading(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _elements(self) -> list:
        printed = LabelledQuotationPage(self._directory)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        return page_assembler(layer, keep_everything()).assemble(printed.blocks, [], SUBLEVEL).elements[1:]

    def test_the_label_stays_in_the_text_between_its_lead_in_and_its_quotation(self) -> None:
        texts = [element.title if isinstance(element, Heading) else element.text for element in self._elements()]
        self.assertEqual([LEAD_IN, LABEL, QUOTATION], texts)

    def test_the_label_opens_no_section(self) -> None:
        self.assertFalse(any(isinstance(element, Heading) for element in self._elements()))


if __name__ == "__main__":
    unittest.main()
