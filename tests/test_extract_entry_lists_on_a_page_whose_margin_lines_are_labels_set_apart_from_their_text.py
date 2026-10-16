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

FILE_PAGE = 1
FONT = "helv"
FONT_SIZE = 9.0
LINE_PITCH = 10.0
GROUP_SPACING = 8.0
FIRST_BASELINE = 100.0
MARGIN = 54.0
WIDE_TEXT_LEFT = 128.0
NARROW_TEXT_LEFT = 70.0
PAGE_WIDTH, PAGE_HEIGHT = 432.0, 648.0
FULL_LINE = "Collected papers on logic and method, with notes by"
WIDE_LABELLED = [("AB", "Cambridge: Cambridge University Press."), ("CD", "Oxford: Clarendon Press."),
                 ("EF", "Paris: Vrin."), ("GH", "Indianapolis: Hackett."), ("HK", "London: Routledge.")]
NARROW_LABELLED = [("Q", "Questions on the Nature of Inference"), ("R", "Remarks on Method")]
EXPECTED = [f"{label} {text}" for label, text in NARROW_LABELLED]


class LabelledAbbreviationsPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE
        self._page = None
        self.narrow_box = Box(0.0, 0.0, 0.0, 0.0)

    def write(self) -> Path:
        with pymupdf.open() as document:
            self._page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for label, imprint in WIDE_LABELLED:
                self._row(label, WIDE_TEXT_LEFT, FULL_LINE)
                self._line(WIDE_TEXT_LEFT, imprint)
            self._baseline += GROUP_SPACING
            self._narrow_group()
            document.save(self._path)
        return self._path

    def _narrow_group(self) -> None:
        top = self._baseline - LINE_PITCH
        for label, text in NARROW_LABELLED:
            self._row(label, NARROW_TEXT_LEFT, text)
        self.narrow_box = Box(MARGIN - 1, top, PAGE_WIDTH / 2, self._baseline)

    def _row(self, label: str, text_left: float, text: str) -> None:
        self._page.insert_text((MARGIN, self._baseline), label, fontsize=FONT_SIZE, fontname=FONT)
        self._line(text_left, text)

    def _line(self, left: float, text: str) -> None:
        self._page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH


class TestEntryListsOnAPageWhoseMarginLinesAreLabelsSetApartFromTheirText(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.pdf = LabelledAbbreviationsPdf(Path(directory.name) / "abbreviations.pdf")
        self.layer = TextLayer(self.pdf.write())
        self.addCleanup(self.layer.close)

    def test_each_row_ending_short_of_the_measure_the_labelled_rows_reach_ends_its_entry(self) -> None:
        entries = HangingIndentList(self.layer).boxed_entries(FILE_PAGE, [self.pdf.narrow_box])
        self.assertEqual(EXPECTED, [" ".join(entry.text.split()) for entry in entries])


if __name__ == "__main__":
    unittest.main()
