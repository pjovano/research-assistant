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
FIRST_LINE_INDENT = 9.5
TAB_STOP = MARGIN + 150.0
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
ROWS = [[["1. The first note runs across the whole measure of the page", "and on to a second line."]],
        [["2. Ibid., p. 4."], ["3. Ibid., p. 9."]],
        [["4. Ibid."], ["5. Ibid., p. 12."]],
        [["6. Ibid., p. 15."], ["7. Ibid., p. 16."]],
        [["8. A middle note that again runs past the tab stop of the row"]],
        [["9. Ibid., p. 20."], ["10. Ibid., p. 21."]],
        [["11. Ibid."], ["12. Ibid., p. 30."]],
        [["13. The last note runs across the measure of the page as well."]]]
EXPECTED = [" ".join(note) for row in ROWS for note in row]


def unspaced(text: str) -> str:
    return "".join(text.split())


class TwoAcrossNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row in ROWS:
                self._row(page, row)
            document.save(self._path)
        return self._path

    def _row(self, page, notes: list[list[str]]) -> None:
        for opening_left, note in zip((MARGIN + FIRST_LINE_INDENT, TAB_STOP), notes):
            for position, line in enumerate(note):
                left = opening_left if position == 0 else MARGIN
                origin = (left, self._baseline + position * LINE_PITCH)
                page.insert_text(origin, line, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH * max(len(note) for note in notes)


class TestEntryListsSettingTwoNotesOnOneRow(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(TwoAcrossNotesPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(self.layer.close)
        self.entries = HangingIndentList(self.layer).boxed_entries(1, [WHOLE_PAGE])

    def test_each_note_opens_its_own_entry_in_reading_order(self) -> None:
        self.assertEqual(EXPECTED, [" ".join(entry.text.split()) for entry in self.entries])

    def test_each_entry_box_holds_only_its_own_note(self) -> None:
        boxed = [unspaced("".join(char.char for char in self.layer.chars_in(1, entry.bbox))) for entry in self.entries]
        self.assertEqual([unspaced(note) for note in EXPECTED], boxed)


if __name__ == "__main__":
    unittest.main()
