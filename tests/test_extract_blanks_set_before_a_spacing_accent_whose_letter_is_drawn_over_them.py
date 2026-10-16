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
FONT_SIZE = 10.5
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
DIAERESIS = "¨"
LETTER_DRAWN_BACK = 0.1
BEFORE_THE_ACCENT = "the seminary at T"
WORD_GAP = " "
AFTER_THE_ACCENT = "ubingen was old"


class AccentedWordPdf:
    def __init__(self, path: Path, letter_offset_from_blank: float) -> None:
        self._path = path
        self._letter_offset_from_blank = letter_offset_from_blank
        self._font = pymupdf.Font(BUILTIN_FONT)
        self._left = LEFT

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_font(fontname=EMBEDDED_FONT, fontbuffer=self._font.buffer)
            self._put(page, BEFORE_THE_ACCENT)
            blank_left = self._left
            self._put(page, WORD_GAP)
            self._put(page, DIAERESIS)
            self._left = blank_left + self._letter_offset_from_blank
            self._put(page, AFTER_THE_ACCENT)
            document.save(self._path)
        return self._path

    def _put(self, page, text: str) -> None:
        page.insert_text((self._left, BASELINE), text, fontsize=FONT_SIZE, fontname=EMBEDDED_FONT)
        self._left += self._font.text_length(text, fontsize=FONT_SIZE)


class TestBlanksSetBeforeASpacingAccentWhoseLetterIsDrawnOverThem(unittest.TestCase):
    def written(self, letter_offset_from_blank: float) -> str:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(AccentedWordPdf(Path(directory) / "accent.pdf", letter_offset_from_blank).write())
            try:
                return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
            finally:
                layer.close()

    def test_a_blank_the_accented_letter_is_drawn_back_over_joins_the_word(self) -> None:
        self.assertEqual("the seminary at Tübingen was old", self.written(LETTER_DRAWN_BACK))

    def test_a_blank_the_accented_letter_is_drawn_after_stays_a_word_gap(self) -> None:
        blank_width = pymupdf.Font(BUILTIN_FONT).text_length(WORD_GAP, fontsize=FONT_SIZE)
        self.assertEqual("the seminary at T übingen was old", self.written(blank_width))


if __name__ == "__main__":
    unittest.main()
