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
MEASURE_CHARS = 56
INDENT_CHARS = 4
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
ENTRIES = [["Abbott, R. 2011. Lanterns and Ledgers: An Es-", "say on Measurement. Harbour Press."],
           ["Brand, S. 2014. Rivers of Account. Journal", "of Studies 4 (2):11-19."],
           ["Carver, T. 2016. Short Titles. Review."],
           ["Dunmore, L. 2019. The Long Entry that Runs",
            "Over Three Lines of Type Because Its Title", "Runs Past the Measure. Review 7 (1):1-9."]]
EXPECTED = ["Abbott, R. 2011. Lanterns and Ledgers: An Essay on Measurement. Harbour Press.",
            "Brand, S. 2014. Rivers of Account. Journal of Studies 4 (2):11-19.",
            "Carver, T. 2016. Short Titles. Review.",
            "Dunmore, L. 2019. The Long Entry that Runs Over Three Lines of Type Because Its Title Runs Past the "
            "Measure. Review 7 (1):1-9."]


def justified(line: str, width_chars: int) -> str:
    words = line.split()
    spaces = [" "] * (len(words) - 1)
    for position in range(width_chars - len(line)):
        spaces[position % len(spaces)] += " "
    return "".join(word + space for word, space in zip(words, spaces + [""]))


class IndentedEntriesPdf:
    def __init__(self, path: Path, opening_indent_chars: int, run_on_indent_chars: int) -> None:
        self._path = path
        self._opening_indent_chars = opening_indent_chars
        self._run_on_indent_chars = run_on_indent_chars
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for entry in ENTRIES:
                self._entry(page, entry)
            document.save(self._path)
        return self._path

    def _entry(self, page, lines: list[str]) -> None:
        indents = [self._opening_indent_chars] + [self._run_on_indent_chars] * (len(lines) - 1)
        last = len(lines) - 1
        for position, (indent_chars, line) in enumerate(zip(indents, lines)):
            text = line if position == last else justified(line, MEASURE_CHARS - indent_chars)
            self._line(page, indent_chars, text)

    def _line(self, page, indent_chars: int, text: str) -> None:
        left = MARGIN + pymupdf.get_text_length(" " * indent_chars, FONT, FONT_SIZE)
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH


class TestEntriesSetWithAFirstLineIndent(unittest.TestCase):
    OPENING_INDENT_CHARS = INDENT_CHARS
    RUN_ON_INDENT_CHARS = 0

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        pdf = IndentedEntriesPdf(Path(directory.name) / "entries.pdf", self.OPENING_INDENT_CHARS,
                                 self.RUN_ON_INDENT_CHARS)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        self.entries = [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]

    def test_each_entry_holds_its_wrapped_lines(self) -> None:
        self.assertEqual(EXPECTED, self.entries)


class TestEntriesSetWithAHangingIndent(TestEntriesSetWithAFirstLineIndent):
    OPENING_INDENT_CHARS = 0
    RUN_ON_INDENT_CHARS = INDENT_CHARS


if __name__ == "__main__":
    unittest.main()
