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
FONT_SIZE = 10.0
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)


class TwoLinePdf:
    def __init__(self, path: Path, lines: list[str]) -> None:
        self._path = path
        self._lines = lines

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, line in enumerate(self._lines):
                page.insert_text((LEFT, FIRST_BASELINE + row * LINE_PITCH), line, fontname=FONT, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def written(lines: list[str]) -> str:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(TwoLinePdf(Path(directory) / "hyphens.pdf", lines).write())
        text = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
        layer.close()
    return text


class TestLineEndHyphensAfterASingleLetter(unittest.TestCase):
    def test_the_hyphen_after_a_single_letter_is_kept(self) -> None:
        self.assertEqual("the Ramsey sentence of the t-terms of a theory",
                         written(["the Ramsey sentence of the t-", "terms of a theory"]))

    def test_the_hyphen_after_two_letters_still_joins_the_word(self) -> None:
        self.assertEqual("a theory reads the other terms", written(["a theory reads the ot-", "her terms"]))


if __name__ == "__main__":
    unittest.main()
