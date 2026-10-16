from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import INLINE_MATH_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
SIZE = 10.0
RULE_WIDTH = 0.4
LEFT = 72.0
RIGHT = 460.0
LINE_PITCH = 13.0
OPENING_BASELINE = 100.0
NUMERATOR_BASELINE = OPENING_BASELINE + LINE_PITCH
DENOMINATOR_BASELINE = NUMERATOR_BASELINE + LINE_PITCH
CLOSING_BASELINE = DENOMINATOR_BASELINE + LINE_PITCH
RULE_DROP = 3.0
BLOCK_ASCENT = 10.0
BLOCK_DESCENT = 4.0
TERM_INDENT = 20.0
OPENING_LINE = "The chance of the outcome is the ratio"
CLOSING_LINE = "and is thus one in four."
ENGINE_READING = "the engine's own reading of the line"
ENGINE_HTML = f"<p>{ENGINE_READING}</p>"
WORDED_TERMS = ("the number of cases in which the outcome holds", "the number of all the cases there are to count")
SPACED_SYMBOL_TERMS = ("a + b", "c - d")


def _width(text: str) -> float:
    return pymupdf.get_text_length(text, FONT, SIZE)


def _draw_fraction(page, terms: tuple[str, str]) -> None:
    rule_width = max(map(_width, terms))
    left = LEFT + TERM_INDENT
    for term, baseline in zip(terms, (NUMERATOR_BASELINE, DENOMINATOR_BASELINE)):
        page.insert_text((left + (rule_width - _width(term)) / 2, baseline), term, fontsize=SIZE, fontname=FONT)
    rule_y = NUMERATOR_BASELINE + RULE_DROP
    page.draw_line((left, rule_y), (left + rule_width, rule_y), width=RULE_WIDTH)


def _block(index: int, kind: str, top_and_last_baseline: tuple[float, float]) -> Block:
    top, last_baseline = top_and_last_baseline
    box = (LEFT - 1, top, RIGHT, last_baseline + BLOCK_DESCENT)
    return Block(1, kind, ENGINE_HTML, box, {}, f"/page/1/{kind}/{index}")


def _engine_blocks_splitting_the_fraction() -> list[Block]:
    return [_block(0, TEXT_KIND, (OPENING_BASELINE - BLOCK_ASCENT, OPENING_BASELINE)),
            _block(1, INLINE_MATH_KIND, (NUMERATOR_BASELINE - BLOCK_ASCENT, DENOMINATOR_BASELINE)),
            _block(2, TEXT_KIND, (NUMERATOR_BASELINE, DENOMINATOR_BASELINE)),
            _block(3, TEXT_KIND, (CLOSING_BASELINE - BLOCK_ASCENT, CLOSING_BASELINE))]


def _texts_of(path: Path, terms: tuple[str, str]) -> list[str]:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((LEFT, OPENING_BASELINE), OPENING_LINE, fontsize=SIZE, fontname=FONT)
        _draw_fraction(page, terms)
        page.insert_text((LEFT, CLOSING_BASELINE), CLOSING_LINE, fontsize=SIZE, fontname=FONT)
        document.save(path)
    layer = TextLayer(path)
    try:
        inputs = StructureInputs(DocumentBlocks([PageBlocks(1, _engine_blocks_splitting_the_fraction())]), [], WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [element.text for element in elements if getattr(element, "text", "")]
    finally:
        layer.close()


class TestFractionsOfWordsSetOverAndUnderADrawnRule(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "fraction.pdf"

    def test_a_fraction_of_words_reads_once_with_its_word_spaces(self) -> None:
        numerator, denominator = WORDED_TERMS
        written = " ".join(_texts_of(self._path, WORDED_TERMS))
        self.assertEqual(1, written.count(f"$\\frac{{\\text{{{numerator}}}}}{{\\text{{{denominator}}}}}$"))
        self.assertEqual(1, written.count(numerator))
        self.assertNotIn(ENGINE_READING, written)

    def test_a_fraction_of_spaced_symbols_stays_a_formula(self) -> None:
        written = " ".join(_texts_of(self._path, SPACED_SYMBOL_TERMS))
        self.assertIn("$\\frac{a+b}{c-d}$", written)
        self.assertNotIn("\\text", written)


if __name__ == "__main__":
    unittest.main()
