from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace, PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading, Paragraph

FONT = "tiro"
BODY_SIZE = 10.0
SYMBOL_SIZE = 14.0
INVISIBLE = 3
LEFT = 40.0
RIGHT = 500.0
CENTRED_LEFT = 260.0
LINE_HALF_HEIGHT = 6.0
FILE_PAGE = 1
SUBLEVEL = 1
OPENING = "Suppose then that we transfer his doctrine about geometric demonstration to number theory."
CLOSING = "The objects falling under this concept are of course the natural numbers."
SYMBOL = "N"
OPENING_BASELINE = 80.0
SYMBOL_BASELINE = 120.0
CLOSING_BASELINE = 160.0
ENGINE_FORMULA = r"<math>\mathbb{N}</math>"
DISPLAYED_FORMULA = r"$$\mathbb{N}$$"
TITLE_WITH_NOTATION = r"The concept <math>\mathbb{N}</math>"
WRITTEN_TITLE_WITH_NOTATION = r"The concept $\mathbb{N}$"


class DisplayedSymbolScanPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            lines = [(LEFT, OPENING_BASELINE, OPENING, BODY_SIZE), (CENTRED_LEFT, SYMBOL_BASELINE, SYMBOL, SYMBOL_SIZE),
                     (LEFT, CLOSING_BASELINE, CLOSING, BODY_SIZE)]
            for left, baseline, text, size in lines:
                page.insert_text((left, baseline), text, fontsize=size, fontname=FONT, render_mode=INVISIBLE)
            document.save(self._path)
        return self._path


def line_box(baseline: float) -> tuple:
    return (LEFT, baseline - BODY_SIZE - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


def engine_reading(heading_html: str) -> list[Block]:
    return [BlockPlace(line_box(OPENING_BASELINE), 0).block(TEXT_KIND, f"<p>{OPENING}</p>"),
            BlockPlace(line_box(SYMBOL_BASELINE), 1).block(HEADING_KIND, f"<h2>{heading_html}</h2>"),
            BlockPlace(line_box(CLOSING_BASELINE), 2).block(TEXT_KIND, f"<p>{CLOSING}</p>")]


class TestHeadingsTheEngineReadsHoldingNothingButNotation(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._layer = TextLayer(DisplayedSymbolScanPdf(Path(directory.name) / "scan.pdf").write())
        self.addCleanup(self._layer.close)

    def _written(self, heading_html: str) -> list[tuple[str, str]]:
        assembler = page_assembler(self._layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        result = assembler.assemble(PageBlocks(FILE_PAGE, engine_reading(heading_html)), [], SUBLEVEL)
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in result.elements if isinstance(element, (Heading, Paragraph))]

    def test_a_heading_holding_only_a_formula_is_written_as_a_displayed_formula(self) -> None:
        self.assertEqual([(Paragraph.__name__, OPENING), (Paragraph.__name__, DISPLAYED_FORMULA),
                          (Paragraph.__name__, CLOSING)], self._written(ENGINE_FORMULA))

    def test_a_heading_holding_words_beside_a_formula_stays_a_heading(self) -> None:
        self.assertIn((Heading.__name__, WRITTEN_TITLE_WITH_NOTATION), self._written(TITLE_WITH_NOTATION))


if __name__ == "__main__":
    unittest.main()
