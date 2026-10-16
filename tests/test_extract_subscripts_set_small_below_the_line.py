from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
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
FONT = "tiro"
BODY_SIZE = 10.0
SCRIPT_SIZE = 7.0
BASELINE = 100.0
SCRIPT_SHIFT = 3.5
SLIGHT_SHIFT = 0.5
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)


@dataclass(frozen=True)
class Piece:
    text: str
    size: float = BODY_SIZE
    shift: float = 0.0
    advances: bool = True


class PiecesPdf:
    def __init__(self, path: Path, pieces: list[Piece]) -> None:
        self._path = path
        self._pieces = pieces

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            left = LEFT
            for piece in self._pieces:
                page.insert_text((left, BASELINE + piece.shift), piece.text, fontsize=piece.size, fontname=FONT)
                if piece.advances:
                    left += pymupdf.get_text_length(piece.text, fontname=FONT, fontsize=piece.size)
            document.save(self._path)
        return self._path


def written(pieces: list[Piece]) -> str:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(PiecesPdf(Path(directory) / "scripts.pdf", pieces).write())
        try:
            return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        finally:
            layer.close()


class TestSubscriptsSetSmallBelowTheLine(unittest.TestCase):
    def test_a_small_numeral_set_below_the_line_is_a_subscript(self) -> None:
        pieces = [Piece("the theory H"), Piece("2", SCRIPT_SIZE, SCRIPT_SHIFT), Piece(" holds")]
        self.assertEqual("the theory H<sub>2</sub> holds", written(pieces))

    def test_a_subscript_stacked_under_a_superscript_keeps_both_scripts(self) -> None:
        pieces = [Piece("as Strong as Z"), Piece("+", SCRIPT_SIZE, -SCRIPT_SHIFT, advances=False),
                  Piece("2", SCRIPT_SIZE, SCRIPT_SHIFT), Piece(", in a journal")]
        self.assertEqual("as Strong as Z<sup>+</sup><sub>2</sub>, in a journal", written(pieces))

    def test_a_small_stop_set_below_the_line_is_no_subscript(self) -> None:
        pieces = [Piece("the theory H2"), Piece(".", SCRIPT_SIZE, SCRIPT_SHIFT), Piece(" holds")]
        self.assertEqual("the theory H2. holds", written(pieces))

    def test_small_type_on_the_line_is_no_subscript(self) -> None:
        pieces = [Piece("the "), Piece("NATO", SCRIPT_SIZE), Piece(" treaty")]
        self.assertEqual("the NATO treaty", written(pieces))

    def test_small_type_set_slightly_low_is_no_subscript(self) -> None:
        pieces = [Piece("the "), Piece("NATO", SCRIPT_SIZE, SLIGHT_SHIFT), Piece(" treaty")]
        self.assertEqual("the NATO treaty", written(pieces))


if __name__ == "__main__":
    unittest.main()
