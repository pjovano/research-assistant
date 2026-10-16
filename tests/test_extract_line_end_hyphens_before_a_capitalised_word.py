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


class LinesPdf:
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
        layer = TextLayer(LinesPdf(Path(directory) / "hyphens.pdf", lines).write())
        text = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
        layer.close()
    return text


class TestLineEndHyphensBeforeACapitalisedWord(unittest.TestCase):
    def test_the_hyphen_between_a_lower_case_letter_and_a_capital_is_kept(self) -> None:
        self.assertEqual("Schellings Hegel-Kritik, in a volume.", written(["Schellings Hegel-", "Kritik, in a volume."]))

    def test_the_hyphen_inside_a_name_the_work_prints_whole_elsewhere_still_joins_the_name(self) -> None:
        self.assertEqual("edited by William McNeill, and by McNeill alone.",
                         written(["edited by William Mc-", "Neill, and by McNeill alone."]))

    def test_the_hyphen_inside_a_word_set_in_capitals_still_joins_the_word(self) -> None:
        self.assertEqual("THE PHILOSOPHY OF NATURE", written(["THE PHILO-", "SOPHY OF NATURE"]))

    def test_the_hyphen_before_a_lower_case_letter_still_joins_the_word(self) -> None:
        self.assertEqual("Schellings Hegelkritik, in a volume.", written(["Schellings Hegel-", "kritik, in a volume."]))


if __name__ == "__main__":
    unittest.main()
