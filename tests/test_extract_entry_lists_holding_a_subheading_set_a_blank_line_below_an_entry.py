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
CHAR_WIDTH = 0.6 * FONT_SIZE
LINE_PITCH = 11.0
BLANK_LINE_SKIP = LINE_PITCH
SKIP_SHORT_OF_A_BLANK_LINE = 0.9 * LINE_PITCH
FIRST_BASELINE = 100.0
MARGIN = 59.0
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
FLUSH, RUN_ON_INDENT, SUBHEADING_INDENT = 0, 2, 7
ENTRY_ABOVE = [(FLUSH, "Wundt, Max. Die deutsche Schulmetaphysik des 17. Jahrhunderts."),
               (RUN_ON_INDENT, "Tubingen: J. C. B. Mohr, 1945.")]
SUBHEADING = [(SUBHEADING_INDENT, "iv. biography, general works, single- and multiple-author"),
              (SUBHEADING_INDENT, "collections of articles on multiple issues")]
ENTRY_BELOW = [(FLUSH, "Allison, Henry E. Idealism and Freedom: Essays on Kant's Theoretical"),
               (RUN_ON_INDENT, "and Practical Philosophy. Cambridge University Press, 1996.")]


def piece_text(piece: list[tuple[int, str]]) -> str:
    return " ".join(text for _indent, text in piece)


class SubheadedEntriesPdf:
    def __init__(self, path: Path, skip_above_the_subheading: float) -> None:
        self._path = path
        self._skip = skip_above_the_subheading
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._set(page, ENTRY_ABOVE)
            self._baseline += self._skip
            self._set(page, SUBHEADING)
            self._baseline += self._skip
            self._set(page, ENTRY_BELOW)
            document.save(self._path)
        return self._path

    def _set(self, page, piece: list[tuple[int, str]]) -> None:
        for indent, text in piece:
            page.insert_text((MARGIN + indent * CHAR_WIDTH, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
            self._baseline += LINE_PITCH


class TestEntryListsHoldingASubheadingSetABlankLineBelowAnEntry(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def entries(self, skip_above_the_subheading: float) -> list[str]:
        pdf = SubheadedEntriesPdf(self._directory / "entries.pdf", skip_above_the_subheading)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_subheading_set_a_blank_line_below_an_entry_stands_apart_from_it(self) -> None:
        expected = [piece_text(ENTRY_ABOVE), piece_text(SUBHEADING), piece_text(ENTRY_BELOW)]
        self.assertEqual(expected, self.entries(BLANK_LINE_SKIP))

    def test_an_indented_line_set_short_of_a_blank_line_below_an_entry_runs_it_on(self) -> None:
        expected = [piece_text(ENTRY_ABOVE + SUBHEADING), piece_text(ENTRY_BELOW)]
        self.assertEqual(expected, self.entries(SKIP_SHORT_OF_A_BLANK_LINE))


if __name__ == "__main__":
    unittest.main()
