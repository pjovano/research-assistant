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
MEASURE_CHARS = 54
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
FILLS = True
RAGGED = False
APA_ENTRIES = [[("Adams, R. (1955). On Measures. Journal of Philosophy", FILLS), ("12 (1958): 1-20.", RAGGED)],
               [("Baker, S. (1959). On Rivers. Review of Metaphysics", FILLS), ("13 (1959): 4-9.", RAGGED)],
               [("Carter, J. (1960). Short Things. Oxford.", RAGGED)],
               [("Dean, M. (1961). Long Things. Mind 70: 1-5.", RAGGED)]]
CHICAGO_ENTRIES = [[("Adams, R. 1955. On Measures. Journal of Philosophy", FILLS), ("12 (1958): 1-20.", RAGGED)],
                   [("Baker, S. 1959. On Rivers. Review of Metaphysics", FILLS), ("13 (1959): 4-9.", RAGGED)],
                   [("Carter, J. 1960. Short Things. Oxford.", RAGGED)],
                   [("Dean, M. 1961. Long Things. Mind 70: 1-5.", RAGGED)]]
GERMAN_ENTRIES = [[("Adams, Robert (1955): Vom Messen. Zeitschrift für", FILLS), ("12 (1958), S. 1-20.", RAGGED)],
                  [("Baker, G.W.F. (1959): Von Flüssen. Hegel-Studien", FILLS), ("13 (1959), S. 4-9.", RAGGED)],
                  [("Carter, Johann (1960): Kurze Dinge. Berlin.", RAGGED)],
                  [("Dean, Maria (1961): Lange Dinge. Kant-Studien 70.", RAGGED)]]


def expected(entries: list[list[tuple[str, bool]]]) -> list[str]:
    return [" ".join(text for text, _fills in entry) for entry in entries]


def justified(line: str, width_chars: int) -> str:
    words = line.split()
    spaces = [" "] * (len(words) - 1)
    for position in range(width_chars - len(line)):
        spaces[position % len(spaces)] += " "
    return "".join(word + space for word, space in zip(words, spaces + [""]))


class FlushEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, entries: list[list[tuple[str, bool]]]) -> Path:
        lines = [justified(text, MEASURE_CHARS) if fills else text for entry in entries for text, fills in entry]
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, line in enumerate(lines):
                page.insert_text((MARGIN, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE,
                                 fontname=FONT)
            document.save(self._path)
        return self._path


class TestUnnumberedListsWithRunOnLinesOpeningWithConsecutiveNumbers(unittest.TestCase):
    ENTRIES = APA_ENTRIES

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(FlushEntriesPdf(Path(directory.name) / "entries.pdf").write(self.ENTRIES))
        self.addCleanup(layer.close)
        self.list = HangingIndentList(layer)

    def test_each_author_entry_holds_its_run_on_line_opening_with_a_number(self) -> None:
        entries = [" ".join(entry.split()) for entry in self.list.entries(1, WHOLE_PAGE)]
        self.assertEqual(expected(self.ENTRIES), entries)

    def test_the_list_is_not_numbered(self) -> None:
        self.assertFalse(self.list.is_numbered(1, [WHOLE_PAGE]))


class TestChicagoStyleListsWithRunOnLinesOpeningWithConsecutiveNumbers(
        TestUnnumberedListsWithRunOnLinesOpeningWithConsecutiveNumbers):
    ENTRIES = CHICAGO_ENTRIES


class TestGermanStyleListsWithRunOnLinesOpeningWithConsecutiveNumbers(
        TestUnnumberedListsWithRunOnLinesOpeningWithConsecutiveNumbers):
    ENTRIES = GERMAN_ENTRIES


if __name__ == "__main__":
    unittest.main()
