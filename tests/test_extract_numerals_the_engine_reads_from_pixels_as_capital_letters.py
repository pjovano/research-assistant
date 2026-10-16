from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _extract.proseguard import ProseGuard

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)


class PrintedLinePdf:
    def __init__(self, path: Path, line: str) -> None:
        self._path = path
        self._line = line

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_text((LEFT, BASELINE), self._line, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestNumeralsTheEngineReadsFromPixelsAsCapitalLetters(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _layer_html(self, printed: str) -> str:
        layer = TextLayer(PrintedLinePdf(self._directory / "line.pdf", printed).write())
        self.addCleanup(layer.close)
        return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))

    def test_a_section_number_read_with_capital_i_for_the_digit_one_takes_the_text_layers_digits(self) -> None:
        self.assertEqual("<h3>§ 11</h3>", ProseGuard().corrected("<h3>§ II</h3>", self._layer_html("§11")))

    def test_a_numeral_read_with_a_lowercase_l_and_a_capital_o_takes_the_text_layers_digits(self) -> None:
        engine_html = "<p>as shown in chapter lO of the work</p>"
        corrected = ProseGuard().corrected(engine_html, self._layer_html("as shown in chapter 10 of the work"))
        self.assertEqual("<p>as shown in chapter 10 of the work</p>", corrected)

    def test_a_roman_numeral_the_text_layer_also_prints_in_letters_stays(self) -> None:
        self.assertEqual("<h3>§ II</h3>", ProseGuard().corrected("<h3>§ II</h3>", self._layer_html("§ II")))

    def test_letters_facing_digits_they_are_not_confused_with_keep_the_engines_reading(self) -> None:
        self.assertEqual("<h3>§ II</h3>", ProseGuard().corrected("<h3>§ II</h3>", self._layer_html("§12")))


if __name__ == "__main__":
    unittest.main()
