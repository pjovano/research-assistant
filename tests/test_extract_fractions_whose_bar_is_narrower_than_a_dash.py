from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerrules import MIN_DASH_WIDTH
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
BODY_SIZE = 10.0
TERM_SIZE = 7.0
RULE_THICKNESS = 0.45
LEFT = 72.0
BASELINE = 100.0
LINE_PITCH = 12.0
NUMERATOR_RISE = 4.0
DENOMINATOR_DROP = 3.2
RULE_RISE = 2.8
TERM_SPACE = 3.0
BLOCK_RIGHT = 400.0
OPENING_LINE = "We know from elementary calculation that the chances are,"
LEAD = "respectively"
JOINER = "and"
CLOSING = "of drawing such a card."
FRACTIONS = (("1", "4"), ("3", "13"))
SHORT_RULE_WIDTH = MIN_DASH_WIDTH / 2
RULED_WORD = "Author, a title set after a short drawn rule."


def _width(text: str, size: float) -> float:
    return pymupdf.get_text_length(text, FONT, size)


class _Page:
    def __init__(self, page) -> None:
        self._page = page

    def text(self, left: float, baseline: float, text: str) -> float:
        self._page.insert_text((left, baseline), text, fontsize=BODY_SIZE, fontname=FONT)
        return left + _width(text, BODY_SIZE)

    def rule(self, left: float, right: float, y: float) -> None:
        self._page.draw_rect(pymupdf.Rect(left, y, right, y + RULE_THICKNESS), color=None, fill=(0, 0, 0))

    def fraction(self, left: float, numerator: str, denominator: str) -> float:
        width = max(_width(numerator, TERM_SIZE), _width(denominator, TERM_SIZE))
        self.rule(left, left + width, BASELINE - RULE_RISE)
        for term, baseline in ((numerator, BASELINE - NUMERATOR_RISE), (denominator, BASELINE + DENOMINATOR_DROP)):
            term_left = left + (width - _width(term, TERM_SIZE)) / 2
            self._page.insert_text((term_left, baseline), term, fontsize=TERM_SIZE, fontname=FONT)
        return left + width


def _fractions_line(page: _Page) -> None:
    page.text(LEFT, BASELINE - LINE_PITCH, OPENING_LINE)
    left = page.text(LEFT, BASELINE, LEAD) + TERM_SPACE
    left = page.fraction(left, *FRACTIONS[0])
    left = page.text(left + TERM_SPACE, BASELINE, JOINER) + TERM_SPACE
    left = page.fraction(left, *FRACTIONS[1])
    page.text(left + TERM_SPACE, BASELINE, CLOSING)


def _short_ruled_line(page: _Page) -> None:
    rule_right = LEFT + SHORT_RULE_WIDTH
    page.rule(LEFT, rule_right, BASELINE - RULE_RISE)
    page.text(rule_right, BASELINE, RULED_WORD)


def _latex(numerator: str, denominator: str) -> str:
    return f"$\\frac{{{numerator}}}{{{denominator}}}$"


def _paragraph_of(path: Path, draw) -> str:
    with pymupdf.open() as document:
        draw(_Page(document.new_page()))
        document.save(path)
    layer = TextLayer(path)
    try:
        box = (LEFT - 1, BASELINE - 2 * LINE_PITCH, BLOCK_RIGHT, BASELINE + LINE_PITCH)
        block = Block(1, TEXT_KIND, "", box, {}, "/page/1/Text/0")
        inputs = StructureInputs(DocumentBlocks([PageBlocks(1, [block])]), [], WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        paragraph, = [element.text for element in elements if isinstance(element, Paragraph)]
        return paragraph
    finally:
        layer.close()


class TestFractionsWhoseBarIsNarrowerThanADash(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "fractions.pdf"

    def test_each_fraction_over_a_bar_narrower_than_a_dash_reads_as_one_notation_span(self) -> None:
        first, second = (_latex(*terms) for terms in FRACTIONS)
        expected = f"{OPENING_LINE} {LEAD} {first} {JOINER} {second} {CLOSING}"
        self.assertEqual(expected, _paragraph_of(self._path, _fractions_line))

    def test_a_rule_narrower_than_a_dash_before_a_word_writes_no_dash(self) -> None:
        self.assertEqual(RULED_WORD, _paragraph_of(self._path, _short_ruled_line))


if __name__ == "__main__":
    unittest.main()
