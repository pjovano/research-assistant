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
FONT_SIZE = 9.0
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
MARGIN = 63.0
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
LINES_ENDING_SHORT = ["8 See the eighth source, p. 64.",
                      "9 The ninth note opens on this line",
                      "and runs on to a second line, my emphasis.",
                      "10 Ibid., p. 6.",
                      "1 The note whose number lost a digit opens",
                      "on this line and closes on the next.",
                      "12 The twelfth note runs past the others, the longest line of the list",
                      "and ends on a line of its own."]
EXPECTED_ENTRIES = ["8 See the eighth source, p. 64.",
                    "9 The ninth note opens on this line and runs on to a second line, my emphasis.",
                    "10 Ibid., p. 6.",
                    "1 The note whose number lost a digit opens on this line and closes on the next.",
                    "12 The twelfth note runs past the others, the longest line of the list and ends on a line of "
                    "its own."]
LINES_WRAPPING_BEFORE_A_NUMBER = ["3 The third note cites a volume and a year printed in the Review",
                                  "88 (1979), p. 75.",
                                  "4 Ibid., p. 76."]
EXPECTED_WRAPPED_ENTRIES = ["3 The third note cites a volume and a year printed in the Review 88 (1979), p. 75.",
                            "4 Ibid., p. 76."]


class FlushNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, lines: list[str]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, line in enumerate(lines):
                page.insert_text((MARGIN, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE,
                                 fontname=FONT)
            document.save(self._path)
        return self._path


class TestNumberedFlushListsWithLinesEndingShort(unittest.TestCase):
    def _entries(self, lines: list[str]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(FlushNotesPdf(Path(directory) / "notes.pdf").write(lines))
            try:
                return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]
            finally:
                layer.close()

    def test_each_numbered_entry_holds_its_lines_ending_short_of_the_longest(self) -> None:
        self.assertEqual(EXPECTED_ENTRIES, self._entries(LINES_ENDING_SHORT))

    def test_a_number_opening_a_line_after_a_line_reaching_the_edge_stays_in_its_entry(self) -> None:
        self.assertEqual(EXPECTED_WRAPPED_ENTRIES, self._entries(LINES_WRAPPING_BEFORE_A_NUMBER))


if __name__ == "__main__":
    unittest.main()
