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
MEASURE_CHARS = 48
INDENT_CHARS = 4
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
FILLS = True
RAGGED = False

FILLED_SINGLE_ENTRY = [("Adams, R. 1990. Short Matters. Oxford.", FILLS)]
SECOND_FILLED_SINGLE_ENTRY = [("Carter, J. 1985. The Widest Of All. York.", FILLS)]
THIRD_FILLED_SINGLE_ENTRY = [("Evans, P. 1979. A Single Line. Leeds.", FILLS)]
RAGGED_WRAPPED_ENTRY = [("Baker, S. 1991. A Book Whose Title Runs", RAGGED), ("On Past the Line. Cambridge.", RAGGED)]
SECOND_RAGGED_WRAPPED_ENTRY = [("Clark, T. 1992. Another Book on", RAGGED), ("Things. London.", RAGGED)]
FILLED_WRAPPED_ENTRY = [("Dean, M. 1988. A Title That Fills the Whole", FILLS), ("Measure. Bristol.", RAGGED)]
SECOND_FILLED_WRAPPED_ENTRY = [("Ford, K. 1994. Another Title Filling the", FILLS), ("Line. Dublin.", RAGGED)]
THREE_LINE_FILLED_ENTRY = [("Grant, L. 2001. The Entry That Runs Over", FILLS),
                           ("Three Lines of Type Because Its Long Title", FILLS), ("Runs On. Exeter.", RAGGED)]
SHORT_ENTRY = [("Hale, N. 2003. Brief. Bath.", RAGGED)]

TWO_FLUSH_RUN_ONS = [FILLED_SINGLE_ENTRY, RAGGED_WRAPPED_ENTRY, SECOND_FILLED_SINGLE_ENTRY,
                     SECOND_RAGGED_WRAPPED_ENTRY]
THREE_FLUSH_AGAINST_TWO_INDENTED = [FILLED_SINGLE_ENTRY, FILLED_WRAPPED_ENTRY, SECOND_FILLED_SINGLE_ENTRY,
                                    SECOND_FILLED_WRAPPED_ENTRY, THIRD_FILLED_SINGLE_ENTRY, SHORT_ENTRY]
THREE_FLUSH_RUN_ONS = [FILLED_WRAPPED_ENTRY, THREE_LINE_FILLED_ENTRY, SHORT_ENTRY]
THREE_FLUSH_AGAINST_ONE_INDENTED = [FILLED_WRAPPED_ENTRY, FILLED_SINGLE_ENTRY, THREE_LINE_FILLED_ENTRY, SHORT_ENTRY]


def justified(line: str, width_chars: int) -> str:
    words = line.split()
    spaces = [" "] * (len(words) - 1)
    for position in range(width_chars - len(line)):
        spaces[position % len(spaces)] += " "
    return "".join(word + space for word, space in zip(words, spaces + [""]))


def expected(entries: list[list[tuple[str, bool]]]) -> list[str]:
    return [" ".join(text for text, _fills in entry) for entry in entries]


class EntryListPdf:
    def __init__(self, path: Path, hangs: bool) -> None:
        self._path = path
        self._hangs = hangs
        self._baseline = FIRST_BASELINE

    def write(self, entries: list[list[tuple[str, bool]]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for entry in entries:
                for position, line in enumerate(entry):
                    self._line(page, self._indent_chars(position), line)
            document.save(self._path)
        return self._path

    def _indent_chars(self, position: int) -> int:
        runs_on = position > 0
        return INDENT_CHARS if runs_on == self._hangs else 0

    def _line(self, page, indent_chars: int, line: tuple[str, bool]) -> None:
        text, fills = line
        shown = justified(text, MEASURE_CHARS - indent_chars) if fills else text
        left = MARGIN + pymupdf.get_text_length(" " * indent_chars, FONT, FONT_SIZE)
        page.insert_text((left, self._baseline), shown, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH


class TestEntryListsWithFewFlushRunOnLines(unittest.TestCase):
    def _entries(self, entries: list[list[tuple[str, bool]]], hangs: bool) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(EntryListPdf(Path(directory) / "entries.pdf", hangs).write(entries))
            try:
                return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]
            finally:
                layer.close()

    def test_a_ragged_hanging_list_with_two_filled_lines_before_flush_openings_keeps_its_entries(self) -> None:
        self.assertEqual(expected(TWO_FLUSH_RUN_ONS), self._entries(TWO_FLUSH_RUN_ONS, hangs=True))

    def test_a_hanging_list_whose_flush_lines_after_filled_lines_barely_outnumber_its_indented_ones_keeps_its_entries(
            self) -> None:
        self.assertEqual(expected(THREE_FLUSH_AGAINST_TWO_INDENTED),
                         self._entries(THREE_FLUSH_AGAINST_TWO_INDENTED, hangs=True))

    def test_a_first_line_indent_list_with_three_flush_run_on_lines_holds_its_wrapped_lines(self) -> None:
        self.assertEqual(expected(THREE_FLUSH_RUN_ONS), self._entries(THREE_FLUSH_RUN_ONS, hangs=False))

    def test_a_first_line_indent_list_with_three_flush_run_on_lines_against_one_indented_holds_its_wrapped_lines(
            self) -> None:
        self.assertEqual(expected(THREE_FLUSH_AGAINST_ONE_INDENTED),
                         self._entries(THREE_FLUSH_AGAINST_ONE_INDENTED, hangs=False))


if __name__ == "__main__":
    unittest.main()
