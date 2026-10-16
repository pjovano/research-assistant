from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import EQUATION_KIND, FOOTNOTE_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "cour"
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY_SIZE = 10.0
SCRIPT_SIZE = 7.6
NOTE_SIZE = 8.0
NOTE_NUMERAL_SIZE = 6.0
SCRIPT_DROP = 1.5
NOTE_NUMERAL_RISE = 2.0
BODY = "Local consistency is the condition that for all contexts"
BODY_BASELINE = 100.0
FORMULA_LEFT = 150.0
FORMULA_BASELINE = 520.0
FORMULA_RUNS = [("d", False), ("CDE", True), (" = ", False), ("e", False), ("CDE", True)]
FORMULA_TEXT = "dCDE = eCDE"
NOTE_NUMERAL = "1"
NOTE_TEXT = "We assume discrete distributions throughout this chapter."
NOTE_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0


class FormulaAboveTheFootnotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, BODY_BASELINE), BODY, fontsize=BODY_SIZE, fontname=FONT)
            self._write_formula(page)
            page.insert_text((LEFT, NOTE_BASELINE - NOTE_NUMERAL_RISE), NOTE_NUMERAL, fontsize=NOTE_NUMERAL_SIZE,
                             fontname=FONT)
            note_left = LEFT + pymupdf.get_text_length(NOTE_NUMERAL, fontname=FONT, fontsize=NOTE_NUMERAL_SIZE)
            page.insert_text((note_left, NOTE_BASELINE), NOTE_TEXT, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _write_formula(page) -> None:
        left = FORMULA_LEFT
        for text, is_a_subscript in FORMULA_RUNS:
            size = SCRIPT_SIZE if is_a_subscript else BODY_SIZE
            baseline = FORMULA_BASELINE + (SCRIPT_DROP if is_a_subscript else 0.0)
            page.insert_text((left, baseline), text, fontsize=size, fontname=FONT)
            left += pymupdf.get_text_length(text, fontname=FONT, fontsize=size)


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


class TestDisplayedFormulasWhoseSubscriptsOutnumberTheirFullSizeCharactersAboveTheFootnotes(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(FormulaAboveTheFootnotesPdf(Path(directory.name) / "formula.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        blocks = [engine_block(TEXT_KIND, f"<p>{BODY}</p>", BODY_BASELINE),
                  engine_block(EQUATION_KIND, f"<p>{FORMULA_TEXT}</p>", FORMULA_BASELINE),
                  engine_block(FOOTNOTE_KIND, f"<p><sup>{NOTE_NUMERAL}</sup> {NOTE_TEXT}</p>", NOTE_BASELINE)]
        self.result = assembler.assemble(PageBlocks(1, blocks), [], 1)

    def test_the_formula_stays_in_the_body(self) -> None:
        paragraphs = [element.text for element in self.result.elements if isinstance(element, Paragraph)]
        self.assertTrue(any("CDE" in paragraph for paragraph in paragraphs), paragraphs)

    def test_the_footnote_below_the_formula_carries_none_of_it(self) -> None:
        texts = [definition.text for definition in self.result.definitions]
        self.assertEqual([], [text for text in texts if "CDE" in text])


if __name__ == "__main__":
    unittest.main()
