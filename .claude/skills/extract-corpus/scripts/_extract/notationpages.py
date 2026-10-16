from __future__ import annotations

from pathlib import Path

import math_fonts

from _extract.layer import TextLayer
from _extract.layerlines import WHOLE_PAGE

MIN_NOTATION_CHARACTERS = 5
FIRST_PAGE = 1
OPERATOR_RANGES = ((0x2190, 0x2300), (0x27C0, 0x2800), (0x2900, 0x2B00), (0x1D400, 0x1D800))


def is_notation_page(chars: list, is_math_font) -> bool:
    notation = sum(1 for char in chars if not char.is_blank and (is_math_font(char.font) or _is_operator(char.char)))
    return notation >= MIN_NOTATION_CHARACTERS


def _is_operator(char: str) -> bool:
    return len(char) == 1 and any(start <= ord(char) < end for start, end in OPERATOR_RANGES)


class NotationPagePlan:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def pages(self) -> list[int]:
        layer = TextLayer(self._pdf_path)
        fonts = math_fonts.MathFonts(self._pdf_path)
        return [page for page in range(FIRST_PAGE, layer.page_count() + 1)
                if is_notation_page(layer.chars_in(page, WHOLE_PAGE), fonts.is_math)]
