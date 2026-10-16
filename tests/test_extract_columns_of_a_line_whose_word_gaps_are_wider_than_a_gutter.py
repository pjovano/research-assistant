from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of

FONT = "helv"
FONT_SIZE = 10.0
LEFT = 60.0
FIRST_BASELINE = 110.0
LINE_PITCH = 12.5
WIDE_WORD_GAP = 14.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
SPREAD_LINE = ("Hypothesis", "one:", "phenomenal", "bonding", "properties =")
WRAPPED_WORD = "o-experience."


class SpreadDisplayLinePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            self._spread(page, SPREAD_LINE, FIRST_BASELINE)
            page.insert_text((LEFT, FIRST_BASELINE + LINE_PITCH), WRAPPED_WORD, fontname=FONT, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _spread(page, words: tuple[str, ...], baseline: float) -> None:
        left = LEFT
        for word in words:
            page.insert_text((left, baseline), word, fontname=FONT, fontsize=FONT_SIZE)
            left += pymupdf.get_text_length(word, fontname=FONT, fontsize=FONT_SIZE) + WIDE_WORD_GAP


class _UnhyphenatedJoins:
    @staticmethod
    def keeps_hyphen(_text: str, _line: str) -> bool:
        return True


class TestColumnsOfALineWhoseWordGapsAreWiderThanAGutter(unittest.TestCase):
    def test_a_spread_line_and_the_line_below_it_are_read_as_two_rows_not_two_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(SpreadDisplayLinePdf(Path(directory) / "spread.pdf").write())
            rows = rows_of(layer.chars_in(1, WHOLE_PAGE))
            layer.close()
        texts = [BlockHtml(_UnhyphenatedJoins()).of([row]) for row in rows]
        self.assertEqual([" ".join(SPREAD_LINE), WRAPPED_WORD], texts)


if __name__ == "__main__":
    unittest.main()
