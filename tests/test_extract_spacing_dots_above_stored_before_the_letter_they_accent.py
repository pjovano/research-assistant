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

FILE_PAGE = 1
BUILTIN_FONT = "tiro"
EMBEDDED_FONT = "F0"
FONT_SIZE = 10.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
DOT_ABOVE = "˙"
BEFORE_THE_ACCENT = "Ersoy,"
WORD_GAP = " "
AFTER_THE_ACCENT = "I. 1998."
ROUNDED_SHORT_OF_THE_DOT = 0.01
DRAWN_BACK_OVER_THE_GAP = 2.0


class DottedInitialPdf:
    def __init__(self, path: Path, letter_drawn_back: float) -> None:
        self._path = path
        self._letter_drawn_back = letter_drawn_back
        self._font = pymupdf.Font(BUILTIN_FONT)
        self._left = LEFT

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_font(fontname=EMBEDDED_FONT, fontbuffer=self._font.buffer)
            self._put(page, BEFORE_THE_ACCENT + WORD_GAP)
            dot_left = self._left
            self._put(page, DOT_ABOVE)
            self._left = dot_left - self._letter_drawn_back
            self._put(page, AFTER_THE_ACCENT)
            document.save(self._path)
        return self._path

    def _put(self, page, text: str) -> None:
        page.insert_text((self._left, BASELINE), text, fontsize=FONT_SIZE, fontname=EMBEDDED_FONT)
        self._left += self._font.text_length(text, fontsize=FONT_SIZE)


class TestSpacingDotsAboveStoredBeforeTheLetterTheyAccent(unittest.TestCase):
    def written(self, letter_drawn_back: float) -> str:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(DottedInitialPdf(Path(directory) / "dotted.pdf", letter_drawn_back).write())
            try:
                return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
            finally:
                layer.close()

    def test_the_dot_and_the_capital_drawn_under_it_read_as_the_dotted_capital(self) -> None:
        self.assertEqual("Ersoy, İ. 1998.", self.written(ROUNDED_SHORT_OF_THE_DOT))

    def test_a_capital_drawn_back_over_the_word_gap_joins_the_word_before(self) -> None:
        self.assertEqual("Ersoy,İ. 1998.", self.written(DRAWN_BACK_OVER_THE_GAP))


if __name__ == "__main__":
    unittest.main()
