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
FIRST_LINE_INDENT = 22.0
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
FLUSH_NOTES = [["9. The ninth note opens on this line", "and runs on to a second line, my emphasis."],
               ["10. Ibid., p. 6."],
               ["11. The eleventh note opens on this line", "and closes on the next."],
               ["12. The twelfth note runs past the others, the longest line of the list", "and ends on its own."]]
FIRST_LINE_INDENTED_NOTES = [["1. See Hegel, Werke in zwanzig Baenden, vol. 1,", "pp. 44-47."],
                             ["2. Ibid., p. 12."],
                             ["3. Compare Kant, Kritik der reinen Vernunft, B 131,", "and the remark that follows it."],
                             ["4. Ibid."]]


def expected(notes: list[list[str]]) -> list[str]:
    return [" ".join(lines) for lines in notes]


class StoppedNotesPdf:
    def __init__(self, path: Path, first_line_indent: float) -> None:
        self._path = path
        self._first_line_indent = first_line_indent

    def write(self, notes: list[list[str]]) -> Path:
        placed = [(position, line) for note in notes for position, line in enumerate(note)]
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, (position, line) in enumerate(placed):
                left = MARGIN + (self._first_line_indent if position == 0 else 0.0)
                page.insert_text((left, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestNumberedListsWhoseNumbersCloseWithAStop(unittest.TestCase):
    def _entries(self, notes: list[list[str]], first_line_indent: float) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            pdf = StoppedNotesPdf(Path(directory) / "notes.pdf", first_line_indent).write(notes)
            layer = TextLayer(pdf)
            try:
                return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]
            finally:
                layer.close()

    def test_each_flush_note_holds_its_run_on_line(self) -> None:
        self.assertEqual(expected(FLUSH_NOTES), self._entries(FLUSH_NOTES, 0.0))

    def test_each_note_set_with_a_first_line_indent_opens_at_its_number(self) -> None:
        self.assertEqual(expected(FIRST_LINE_INDENTED_NOTES),
                         self._entries(FIRST_LINE_INDENTED_NOTES, FIRST_LINE_INDENT))


if __name__ == "__main__":
    unittest.main()
