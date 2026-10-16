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

FONT = "helv"
WHOLE_PAGE = Box(0.0, 0.0, 600.0, 800.0)
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 13.0
BODY_SIZE = 10.0
SMALL_SIZE = 7.0
MARK_RISE = 7.0
ROMAN_OPENING = "thus. On the one hand, "
SMALL_CAPITALS = "WILLING ITSELF IS THINKABLE ONLY UNDER THE PRESUPPOSITION"
MARK = "12"
FULL_SIZE_LINE = "of something different from the I, namely, something to be acted upon."


class SmallCapitalLinePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_text((LEFT, FIRST_BASELINE), ROMAN_OPENING, fontname=FONT, fontsize=BODY_SIZE)
            capitals_left = LEFT + pymupdf.get_text_length(ROMAN_OPENING, FONT, BODY_SIZE)
            page.insert_text((capitals_left, FIRST_BASELINE), SMALL_CAPITALS, fontname=FONT, fontsize=SMALL_SIZE)
            page.insert_text((LEFT, FIRST_BASELINE + LINE_PITCH), FULL_SIZE_LINE, fontname=FONT, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path


class MarkOverLinePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            full_baseline = FIRST_BASELINE + LINE_PITCH
            page.insert_text((LEFT, full_baseline), FULL_SIZE_LINE, fontname=FONT, fontsize=BODY_SIZE)
            mark_left = LEFT + pymupdf.get_text_length(FULL_SIZE_LINE, FONT, BODY_SIZE)
            page.insert_text((mark_left, full_baseline - MARK_RISE), MARK, fontname=FONT, fontsize=SMALL_SIZE)
            document.save(self._path)
        return self._path


def written(pdf) -> str:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(pdf(Path(directory) / "lines.pdf").write())
        text = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
        layer.close()
    return text


class TestLinesSetMostlyInSmallCapitalsAFullLineAboveTheNext(unittest.TestCase):
    def test_the_line_reads_before_the_next_line_unraised(self) -> None:
        self.assertEqual(f"{ROMAN_OPENING}{SMALL_CAPITALS} {FULL_SIZE_LINE}", written(SmallCapitalLinePdf))

    def test_a_small_mark_risen_less_than_the_next_lines_type_size_is_still_raised_into_it(self) -> None:
        self.assertEqual(f"{FULL_SIZE_LINE}<sup>{MARK}</sup>", written(MarkOverLinePdf))


if __name__ == "__main__":
    unittest.main()
