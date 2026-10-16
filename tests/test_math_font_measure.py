from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from math_fonts import MathFonts

PROSE_FONT = "helv"
GLYPH_FONT = "tiit"
GLYPH_FAMILY = "Times-Italic"
PROSE_LEFT = 72
GLYPH_LEFT = 420
FIRST_BASELINE = 60
LINE_STEP = 12
GLYPH_BASELINE_SHIFT = 6
PROSE_LINE_CHARS = 50
PROSE_CHARACTER = "x"
AMPLE_PROSE_CHARS = 1000
LETTER = "a"
DIGIT = "7"
LETTER_PAIR = "ab"
FI_LIGATURE = "ﬁ"
MATH_ITALIC_X = "\U0001d465"
ONE_CODE_CMAP = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Remapped def "
                 "1 begincodespacerange <00> <FF> endcodespacerange 1 beginbfchar {pair} endbfchar "
                 "endcmap CMapName currentdict /CMap defineresource pop end end")


@dataclass(frozen=True)
class Column:
    left: int
    font: str
    baseline_shift: int

    def insert(self, page: pymupdf.Page, texts: list[str]) -> None:
        for row, text in enumerate(texts):
            baseline = FIRST_BASELINE + self.baseline_shift + row * LINE_STEP
            page.insert_text((self.left, baseline), text, fontname=self.font)


PROSE_COLUMN = Column(PROSE_LEFT, PROSE_FONT, 0)
GLYPH_COLUMN = Column(GLYPH_LEFT, GLYPH_FONT, GLYPH_BASELINE_SHIFT)


class GlyphFontPdf:
    def __init__(self, case: unittest.TestCase, prose_chars: int, glyph_spans: list[str],
                 stand_in: str | None = None) -> None:
        directory = tempfile.TemporaryDirectory()
        case.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "glyphs.pdf"
        self._stand_in = stand_in
        self._write(prose_chars, glyph_spans)

    def sets_notation_in_the_glyph_font(self) -> bool:
        return MathFonts(self._path).is_math(GLYPH_FAMILY)

    def _write(self, prose_chars: int, glyph_spans: list[str]) -> None:
        with pymupdf.open() as document:
            page = document.new_page()
            PROSE_COLUMN.insert(page, self._prose_lines(prose_chars))
            GLYPH_COLUMN.insert(page, glyph_spans)
            self._remap_glyph_font(document, page)
            document.save(self._path)

    def _remap_glyph_font(self, document: pymupdf.Document, page: pymupdf.Page) -> None:
        if self._stand_in is None:
            return
        font_xref = next(font[0] for font in page.get_fonts() if font[3] == GLYPH_FAMILY)
        cmap_xref = document.get_new_xref()
        document.update_object(cmap_xref, "<<>>")
        pair = f"<{ord(LETTER):02X}> <{ord(self._stand_in):04X}>"
        document.update_stream(cmap_xref, ONE_CODE_CMAP.format(pair=pair).encode("ascii"))
        document.xref_set_key(font_xref, "ToUnicode", f"{cmap_xref} 0 R")

    @staticmethod
    def _prose_lines(prose_chars: int) -> list[str]:
        full_lines, remainder = divmod(prose_chars, PROSE_LINE_CHARS)
        lines = [PROSE_CHARACTER * PROSE_LINE_CHARS] * full_lines
        return lines + [PROSE_CHARACTER * remainder] if remainder else lines


class TestGlyphFontMeasure(unittest.TestCase):
    def _is_math(self, prose_chars: int, glyph_spans: list[str]) -> bool:
        return GlyphFontPdf(self, prose_chars, glyph_spans).sets_notation_in_the_glyph_font()

    def test_twenty_single_letter_spans_are_a_math_font(self) -> None:
        self.assertTrue(self._is_math(AMPLE_PROSE_CHARS, [LETTER] * 20))

    def test_nineteen_spans_are_too_few_to_measure(self) -> None:
        self.assertFalse(self._is_math(AMPLE_PROSE_CHARS, [LETTER] * 19))

    def test_seventeen_single_spans_in_twenty_are_a_math_font(self) -> None:
        self.assertTrue(self._is_math(AMPLE_PROSE_CHARS, [LETTER] * 17 + [LETTER_PAIR] * 3))

    def test_sixteen_single_spans_in_twenty_are_a_prose_font(self) -> None:
        self.assertFalse(self._is_math(AMPLE_PROSE_CHARS, [LETTER] * 16 + [LETTER_PAIR] * 4))

    def test_a_font_half_letters_is_a_math_font(self) -> None:
        self.assertTrue(self._is_math(AMPLE_PROSE_CHARS, [LETTER] * 10 + [DIGIT] * 10))

    def test_a_font_under_half_letters_is_a_prose_font(self) -> None:
        self.assertFalse(self._is_math(AMPLE_PROSE_CHARS, [LETTER] * 9 + [DIGIT] * 11))

    def test_a_font_setting_a_twentieth_of_the_work_is_a_math_font(self) -> None:
        self.assertTrue(self._is_math(380, [LETTER] * 20))

    def test_a_font_setting_over_a_twentieth_of_the_work_is_a_prose_font(self) -> None:
        self.assertFalse(self._is_math(379, [LETTER] * 20))

    def test_a_font_setting_only_ligatures_one_glyph_at_a_time_is_a_prose_font(self) -> None:
        pdf = GlyphFontPdf(self, AMPLE_PROSE_CHARS, [LETTER] * 20, stand_in=FI_LIGATURE)
        self.assertFalse(pdf.sets_notation_in_the_glyph_font())

    def test_a_font_setting_mathematical_italic_letters_one_at_a_time_is_a_math_font(self) -> None:
        pdf = GlyphFontPdf(self, AMPLE_PROSE_CHARS, [LETTER] * 20, stand_in=MATH_ITALIC_X)
        self.assertTrue(pdf.sets_notation_in_the_glyph_font())


if __name__ == "__main__":
    unittest.main()
