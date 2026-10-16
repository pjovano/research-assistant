from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.guardedmath import GuardedMath, NotationLog
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of

FILE_PAGE = 1
PROSE_FONT = "tiro"
SYMBOL_FONT = "symb"
FONT_SIZE = 10.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
OPENING = "so "
EXISTS_CODE = "$"
CLOSING = "x P(x) holds"
ENGINE_HTML = "<p>so <math>\\exists x P(x)</math> holds</p>"


class Pen:
    def __init__(self, page, left: float) -> None:
        self._page = page
        self._left = left

    def write(self, text: str, font: str) -> None:
        self._page.insert_text((self._left, BASELINE), text, fontsize=FONT_SIZE, fontname=font)
        self._left += pymupdf.get_text_length(text, font, FONT_SIZE)


class SymbolFontSentencePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            pen = Pen(document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom), LEFT)
            pen.write(OPENING, PROSE_FONT)
            pen.write(EXISTS_CODE, SYMBOL_FONT)
            pen.write(CLOSING, PROSE_FONT)
            document.save(self._path)
        return self._path


class TestNotationFromASymbolFontEmittingAsciiSymbols(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(SymbolFontSentencePdf(Path(directory.name) / "symbols.pdf").write())
        self.addCleanup(layer.close)
        layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        self.log = NotationLog()
        self.checked = GuardedMath(self.log).checked(FILE_PAGE, ENGINE_HTML, layer_html)

    def test_the_engine_symbol_is_kept_over_the_ascii_symbol_the_text_layer_emits(self) -> None:
        self.assertEqual(ENGINE_HTML, self.checked)

    def test_the_formula_is_flagged(self) -> None:
        self.assertEqual(["file p. 1: flagged \\exists x P(x) (text layer: $x P(x))"], self.log.entries())


if __name__ == "__main__":
    unittest.main()
