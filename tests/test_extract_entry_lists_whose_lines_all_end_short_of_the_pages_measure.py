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
FONT = "cour"
FONT_SIZE = 9.0
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
MARGIN = 63.0
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
BODY_LINE = "The body of the page runs to the full measure of its column, line after line."
BODY_LINES = 6
ENTRIES = ["Alder, F., A Longer Title of a Study (Paris: Presses de France, 1981).",
           "Birch, J., A Shorter Title (Indianapolis: Hackett, 1984)."]
ENTRIES_TOP = FIRST_BASELINE + (BODY_LINES + 1) * LINE_PITCH - LINE_PITCH
ENTRIES_BOX = Box(0.0, ENTRIES_TOP, PAGE_WIDTH, ENTRIES_TOP + len(ENTRIES) * LINE_PITCH + LINE_PITCH)


class BodyAboveEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        lines = [BODY_LINE] * BODY_LINES + [""] + ENTRIES
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, line in enumerate(lines):
                page.insert_text((MARGIN, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE,
                                 fontname=FONT)
            document.save(self._path)
        return self._path


class TestEntryListsWhoseLinesAllEndShortOfThePagesMeasure(unittest.TestCase):
    def test_each_line_ending_short_of_the_measure_the_page_sets_ends_its_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(BodyAboveEntriesPdf(Path(directory) / "entries.pdf").write())
            try:
                self.assertEqual(ENTRIES, HangingIndentList(layer).entries(FILE_PAGE, ENTRIES_BOX))
            finally:
                layer.close()


if __name__ == "__main__":
    unittest.main()
