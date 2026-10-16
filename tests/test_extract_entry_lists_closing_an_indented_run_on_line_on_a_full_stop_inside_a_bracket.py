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
CHAR_WIDTH = pymupdf.get_text_length("x", FONT, FONT_SIZE)
MARGIN = 36.0
MEASURE_CHARS = 84
PAGE_WIDTH, PAGE_HEIGHT = 560.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
FLUSH = 0
RUN_ON = 3
FILLS = True
ENDS_SHORT = False
ENTRIES = [
    [(FLUSH, "Abel, Anna (1970). The first study of the subject. Oxford: Clarendon Press.", ENDS_SHORT)],
    [(FLUSH, "Brandt, Bernd (1979). An Inquiry into the Forms of Exchange, 2 vols., eds.", FILLS),
     (RUN_ON, "C. Dahl and E. Falk. Oxford: Clarendon Press. (Original work published 1776.)", FILLS)],
    [(FLUSH, "Gray, Greta (2003). Historical notes on the lectures and on their", FILLS),
     (RUN_ON, "reception in the schools. Cambridge: Cambridge University Press.", ENDS_SHORT)],
    [(FLUSH, "Hart, Hans (2004). Introduction. Berlin: Walter de Gruyter.", ENDS_SHORT)]]


def justified(line: str, measure_chars: int) -> str:
    words = line.split()
    spaces = measure_chars - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


class HangingEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, entries: list[list[tuple[int, str, bool]]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            lines = [line for entry in entries for line in entry]
            for row, (indent_chars, text, fills) in enumerate(lines):
                printed = justified(text, MEASURE_CHARS - indent_chars) if fills else text
                page.insert_text((MARGIN + indent_chars * CHAR_WIDTH, FIRST_BASELINE + row * LINE_PITCH), printed,
                                 fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def entry_texts(entries: list[list[tuple[int, str, bool]]]) -> list[str]:
    return [" ".join(text for _indent, text, _fills in entry) for entry in entries]


class TestEntryListsClosingAnIndentedRunOnLineOnAFullStopInsideABracket(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "entries.pdf"

    def entries(self) -> list[str]:
        layer = TextLayer(HangingEntriesPdf(self._path).write(ENTRIES))
        self.addCleanup(layer.close)
        return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_run_on_line_filling_the_measure_and_closing_inside_a_bracket_ends_its_entry(self) -> None:
        self.assertEqual(entry_texts(ENTRIES), self.entries())


if __name__ == "__main__":
    unittest.main()
