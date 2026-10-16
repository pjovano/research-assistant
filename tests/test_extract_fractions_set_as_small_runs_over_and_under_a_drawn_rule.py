from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.box import Box
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
BODY_SIZE = 9.0
TERM_SIZE = 6.0
RULE_WIDTH = 0.4
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 11.0
NUMERATOR_RISE = 4.0
DENOMINATOR_DROP = 3.2
RULE_RISE = 2.2
TERM_SPACE = 4.0
BLOCK_RIGHT = 400.0
OPENING_LINE = "5. The logic is what every premise-set implies."
LABEL = "6. "
JOINER = " and "
FRACTIONS = (("A,B|~C", "A&B|~C"), ("|~A,C", "|~AvB,C"))
UNDERLINED = ("an ", "underlined", " word sits above")
NEXT_LINE = "the next line of the paragraph runs on below it"


@dataclass(frozen=True)
class _Fraction:
    numerator: str
    denominator: str

    @property
    def width(self) -> float:
        return max(_width(self.numerator, TERM_SIZE), _width(self.denominator, TERM_SIZE))

    def draw(self, page, left: float, baseline: float) -> None:
        rule_y = baseline - RULE_RISE
        page.draw_line((left, rule_y), (left + self.width, rule_y), width=RULE_WIDTH)
        for term, term_baseline in ((self.numerator, baseline - NUMERATOR_RISE),
                                    (self.denominator, baseline + DENOMINATOR_DROP)):
            term_left = left + (self.width - _width(term, TERM_SIZE)) / 2
            page.insert_text((term_left, term_baseline), term, fontsize=TERM_SIZE, fontname=FONT)

    @property
    def latex(self) -> str:
        return f"$\\frac{{{_escaped(self.numerator)}}}{{{_escaped(self.denominator)}}}$"


def _width(text: str, size: float) -> float:
    return pymupdf.get_text_length(text, FONT, size)


def _escaped(term: str) -> str:
    return term.replace("&", "\\&")


class _Page:
    def __init__(self, page) -> None:
        self._page = page

    def text(self, origin: tuple[float, float], text: str) -> float:
        self._page.insert_text(origin, text, fontsize=BODY_SIZE, fontname=FONT)
        return origin[0] + _width(text, BODY_SIZE)

    def fractions_line(self, baseline: float) -> None:
        left = self.text((LEFT, baseline), LABEL)
        fractions = [_Fraction(*terms) for terms in FRACTIONS]
        for position, fraction in enumerate(fractions):
            fraction.draw(self._page, left, baseline)
            left += fraction.width
            if position < len(fractions) - 1:
                left = self.text((left + TERM_SPACE, baseline), JOINER.strip()) + TERM_SPACE

    def underlined_line(self, baseline: float) -> None:
        left = self.text((LEFT, baseline), UNDERLINED[0])
        right = self.text((left, baseline), UNDERLINED[1])
        self._page.draw_line((left, baseline + RULE_WIDTH * 2), (right, baseline + RULE_WIDTH * 2), width=RULE_WIDTH)
        self.text((right, baseline), UNDERLINED[2])
        self.text((LEFT, baseline + LINE_PITCH), NEXT_LINE)


def _paragraph_of(path: Path, draw) -> str:
    with pymupdf.open() as document:
        draw(_Page(document.new_page()))
        document.save(path)
    layer = TextLayer(path)
    try:
        box = (LEFT - 1, FIRST_BASELINE - 2 * LINE_PITCH, BLOCK_RIGHT, FIRST_BASELINE + 2 * LINE_PITCH)
        block = Block(1, TEXT_KIND, "", box, {}, "/page/1/Text/0")
        inputs = StructureInputs(DocumentBlocks([PageBlocks(1, [block])]), [], WorkerReadings.none(),
                                 keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        paragraph, = [element.text for element in elements if isinstance(element, Paragraph)]
        return paragraph
    finally:
        layer.close()


def _note_with_fractions(page: _Page) -> None:
    page.text((LEFT, FIRST_BASELINE - LINE_PITCH), OPENING_LINE)
    page.fractions_line(FIRST_BASELINE)


class TestFractionsSetAsSmallRunsOverAndUnderADrawnRule(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "fractions.pdf"

    def test_each_fraction_reads_as_one_notation_span_on_its_line(self) -> None:
        latex = [_Fraction(*terms).latex for terms in FRACTIONS]
        paragraph = _paragraph_of(self._path, _note_with_fractions)
        self.assertEqual(f"{OPENING_LINE} {LABEL}{latex[0]}{JOINER}{latex[1]}", paragraph)

    def test_the_unstacked_layer_the_guards_read_keeps_each_term_as_drawn(self) -> None:
        with pymupdf.open() as document:
            _note_with_fractions(_Page(document.new_page()))
            document.save(self._path)
        layer = TextLayer(self._path)
        self.addCleanup(layer.close)
        written = "".join(char.char for char in layer.unstacked().chars_in(1, Box(0.0, 0.0, 600.0, 800.0)))
        self.assertNotIn("\\frac", written)

    def test_an_underlined_word_stays_in_its_line(self) -> None:
        paragraph = _paragraph_of(self._path, lambda page: page.underlined_line(FIRST_BASELINE))
        self.assertEqual(f"{''.join(UNDERLINED)} {NEXT_LINE}", paragraph)


if __name__ == "__main__":
    unittest.main()
