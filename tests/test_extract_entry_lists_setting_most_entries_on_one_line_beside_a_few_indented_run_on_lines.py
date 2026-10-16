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
    [(FLUSH, "Abel, A. (1989). The Critique of Judgment. Berlin: Mayer.", ENDS_SHORT)],
    [(FLUSH, "Baker, B. (1983). A Theory of Concepts. New Haven: Yale University Press.", ENDS_SHORT)],
    [(FLUSH, "Carr, C. (1962). The Theory of Knowledge. London: Routledge and Kegan Paul;", FILLS),
     (RUN_ON, "rpt. New York: Humanities Press, 1973.", ENDS_SHORT)],
    [(FLUSH, "Dunn, D. (1987). Knowledge and Its Claims. Cambridge: Cambridge University.", FILLS)],
    [(FLUSH, "Engel, Eva (1929). The Critique of Practical Reason. London: Macmillan Ltd.", FILLS)],
    [(FLUSH, "Engel, Eva (1998). The Critique of Practical Reason, ed. F. Fox. Cambridge:", FILLS),
     (RUN_ON, "Cambridge University Press.", ENDS_SHORT)],
    [(FLUSH, "Gale, G. (1990). The Psychology of Reason. Oxford: Oxford University Press.", ENDS_SHORT)],
    [(FLUSH, "Hale, H. (1936). The Metaphysics of Experience. London: Allen and Unwin.", ENDS_SHORT)]]


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


class TestEntryListsSettingMostEntriesOnOneLineBesideAFewIndentedRunOnLines(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "entries.pdf"

    def entries(self) -> list[str]:
        layer = TextLayer(HangingEntriesPdf(self._path).write(ENTRIES))
        self.addCleanup(layer.close)
        return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_flush_line_below_a_one_line_entry_filling_the_measure_opens_an_entry(self) -> None:
        self.assertEqual(entry_texts(ENTRIES), self.entries())


if __name__ == "__main__":
    unittest.main()
