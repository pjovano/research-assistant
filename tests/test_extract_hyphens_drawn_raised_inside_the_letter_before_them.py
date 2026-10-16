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

FONT = "tiro"
FONT_SIZE = 9.0
LEFT = 72.0
BASELINE = 100.0
MACRON_RISE = 3.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)


class HyphenDrawnOverLetterPdf:
    def __init__(self, path: Path, pieces: list[tuple[str, bool]]) -> None:
        self._path = path
        self._pieces = pieces

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            left = LEFT
            for text, is_marked in self._pieces:
                left = self._marked(page, left, text) if is_marked else self._put(page, (left, BASELINE), text)
            document.save(self._path)
        return self._path

    def _marked(self, page, left: float, letter: str) -> float:
        right = self._put(page, (left, BASELINE), letter)
        hyphen_width = pymupdf.get_text_length("-", FONT, FONT_SIZE)
        self._put(page, (left + (right - left - hyphen_width) / 2, BASELINE - MACRON_RISE), "-")
        return right

    @staticmethod
    def _put(page, origin: tuple[float, float], text: str) -> float:
        page.insert_text(origin, text, fontname=FONT, fontsize=FONT_SIZE)
        return origin[0] + pymupdf.get_text_length(text, FONT, FONT_SIZE)


def written(pieces: list[tuple[str, bool]]) -> str:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(HyphenDrawnOverLetterPdf(Path(directory) / "macrons.pdf", pieces).write())
        text = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
        layer.close()
    return text


class TestHyphensDrawnRaisedInsideTheLetterBeforeThem(unittest.TestCase):
    def test_the_hyphen_is_a_macron_over_that_letter(self) -> None:
        pieces = [("the N", False), ("a", True), ("g", False), ("a", True), ("rjuna text", False)]
        self.assertEqual("the Nāgārjuna text", written(pieces))

    def test_a_hyphen_set_after_its_letter_stays_a_hyphen(self) -> None:
        self.assertEqual("a well-known text", written([("a well-known text", False)]))


if __name__ == "__main__":
    unittest.main()
