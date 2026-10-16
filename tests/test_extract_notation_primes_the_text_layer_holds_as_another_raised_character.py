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
FONT = "tiro"
FONT_SIZE = 10.0
SCRIPT_SIZE = 7.0
SCRIPT_RISE = 4.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
OPENING = "so q"
RAISED_SHRIEK = "!"
CLOSING = " holds"
ENGINE_HTML = "<p>so <math>q'</math> holds</p>"


class Pen:
    def __init__(self, page, left: float) -> None:
        self._page = page
        self._left = left

    def write(self, text: str, size: float, rise: float = 0.0) -> None:
        self._page.insert_text((self._left, BASELINE - rise), text, fontsize=size, fontname=FONT)
        self._left += pymupdf.get_text_length(text, FONT, size)


class RaisedShriekSentencePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            pen = Pen(document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom), LEFT)
            pen.write(OPENING, FONT_SIZE)
            pen.write(RAISED_SHRIEK, SCRIPT_SIZE, SCRIPT_RISE)
            pen.write(CLOSING, FONT_SIZE)
            document.save(self._path)
        return self._path


class TestNotationPrimesTheTextLayerHoldsAsAnotherRaisedCharacter(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(RaisedShriekSentencePdf(Path(directory.name) / "shriek.pdf").write())
        self.addCleanup(layer.close)
        layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        self.log = NotationLog()
        self.checked = GuardedMath(self.log).checked(FILE_PAGE, ENGINE_HTML, layer_html)

    def test_a_prime_the_text_layer_holds_as_a_shriek_becomes_a_raised_shriek(self) -> None:
        self.assertEqual("<p>so <math>q^{!}</math> holds</p>", self.checked)

    def test_the_raised_correction_is_logged(self) -> None:
        self.assertEqual(["file p. 1: corrected q' to q^{!} (text layer: q!)"], self.log.entries())


if __name__ == "__main__":
    unittest.main()
