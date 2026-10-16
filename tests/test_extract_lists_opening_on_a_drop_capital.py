from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import TextLayer
from _extract.lists import HangingIndentList

FONT = "cour"
BODY_SIZE = 10.0
CAPITAL_SIZE = 40.0
LINE_PITCH = 12.0
FIRST_BASELINE = 100.0
MARGIN = 72.0
CAPITAL_GAP = 2.0
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
CAPITAL = "T"
BESIDE_CAPITAL = ["his brief bibliography includes mainly all recent works,",
                  "English, and the references on each chapter are found in",
                  "the chapters' own references; comprehensive ones are all"]
FLUSH_BELOW = "listed below, in the seventh section."


class DropCapitalParagraphPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            self._capital(page)
            self._beside(page)
            page.insert_text((MARGIN, _baseline_of(len(BESIDE_CAPITAL))), FLUSH_BELOW, fontsize=BODY_SIZE,
                             fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _capital(page) -> None:
        baseline = _baseline_of(len(BESIDE_CAPITAL) - 1)
        page.insert_text((MARGIN, baseline), CAPITAL, fontsize=CAPITAL_SIZE, fontname=FONT)

    @staticmethod
    def _beside(page) -> None:
        left = MARGIN + pymupdf.get_text_length(CAPITAL, FONT, CAPITAL_SIZE) + CAPITAL_GAP
        for row, text in enumerate(BESIDE_CAPITAL):
            page.insert_text((left, _baseline_of(row)), text, fontsize=BODY_SIZE, fontname=FONT)


def _baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class TestListsOpeningOnADropCapital(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(DropCapitalParagraphPdf(Path(directory.name) / "paragraph.pdf").write())
        self.addCleanup(layer.close)
        self.entries = [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]

    def test_the_capital_and_the_lines_beside_and_below_it_read_as_one_entry(self) -> None:
        paragraph = CAPITAL + " ".join(BESIDE_CAPITAL + [FLUSH_BELOW])
        self.assertEqual([paragraph], self.entries)


if __name__ == "__main__":
    unittest.main()
