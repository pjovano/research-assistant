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
INDENT = "    "
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
TWO_WRAPPED_NOTES = [["1 See Hegel, Werke in zwanzig Baenden, vol. 1,", "pp. 44-47."],
                     ["2 Ibid., p. 12."],
                     ["3 Compare Kant, Kritik der reinen Vernunft, B 131,", "and the remark that follows it."],
                     ["4 Ibid."]]
ONE_WRAPPED_NOTE = [["1 See Hegel, Werke in zwanzig Baenden, vol. 1,", "pp. 44-47."],
                    ["2 Ibid., p. 12."],
                    ["3 Ibid., p. 14."],
                    ["4 Ibid."]]


def expected(notes: list[list[str]]) -> list[str]:
    return [" ".join(lines) for lines in notes]


class FirstLineIndentNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, notes: list[list[str]]) -> Path:
        lines = [INDENT + line if position == 0 else line for note in notes for position, line in enumerate(note)]
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, line in enumerate(lines):
                left = MARGIN + pymupdf.get_text_length(line[:len(line) - len(line.lstrip())], FONT, FONT_SIZE)
                page.insert_text((left, FIRST_BASELINE + row * LINE_PITCH), line.lstrip(), fontsize=FONT_SIZE,
                                 fontname=FONT)
            document.save(self._path)
        return self._path


class TestNumberedListsSetWithAFirstLineIndent(unittest.TestCase):
    def _entries(self, notes: list[list[str]]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(FirstLineIndentNotesPdf(Path(directory) / "notes.pdf").write(notes))
            try:
                return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]
            finally:
                layer.close()

    def test_each_note_holds_its_wrapped_line_when_two_notes_wrap(self) -> None:
        self.assertEqual(expected(TWO_WRAPPED_NOTES), self._entries(TWO_WRAPPED_NOTES))

    def test_each_note_opens_at_its_number_when_one_note_wraps(self) -> None:
        self.assertEqual(expected(ONE_WRAPPED_NOTE), self._entries(ONE_WRAPPED_NOTE))


if __name__ == "__main__":
    unittest.main()
