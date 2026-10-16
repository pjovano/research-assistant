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
MARGIN = 63.0
HANGING_INDENT = 9.5
MEASURE_CHARS = 70
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
FILLS, RAGGED = True, False
ENTRIES_ABOVE = [
    (["Abel, Ruth. A Handbook of the Critical Philosophy and its Reception.", "Second edition. Leipzig, 1912."],
     FILLS),
    (["Baumann, Otto. Index to the Collected Writings. Berlin, 1969."], RAGGED),
    (["Christ, Paul. A Dictionary of Critical Philosophy. Six volumes, with", "a supplement. Jena, 1799."],
     FILLS),
]
PARAGRAPH = ["The leading journals for the publication of articles on the subject in",
             "German and English are these two, each published since the late",
             "Nineteenth century by a university press."]
ENTRIES_BELOW = [
    (["Dorn, Anna. Studies in the Philosophy of Nature. Two volumes. Oxford,", "1950."], FILLS),
    (["Ebert, Klaus. The Concept of Freedom. Munich, 1973."], RAGGED),
]


def justified(line: str) -> str:
    words = line.split()
    spaces = MEASURE_CHARS - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


def entry_texts(entries: list[tuple[list[str], bool]]) -> list[str]:
    return [" ".join(lines) for lines, _opening_fills in entries]


class ParagraphBetweenEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._row = 0

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._entries(page, ENTRIES_ABOVE)
            self._paragraph(page)
            self._entries(page, ENTRIES_BELOW)
            document.save(self._path)
        return self._path

    def _entries(self, page, entries: list[tuple[list[str], bool]]) -> None:
        for lines, opening_fills in entries:
            opening, *run_on = lines
            self._line(page, MARGIN, justified(opening) if opening_fills else opening)
            for line in run_on:
                self._line(page, MARGIN + HANGING_INDENT, line)

    def _paragraph(self, page) -> None:
        *filled, last = PARAGRAPH
        for line in filled:
            self._line(page, MARGIN, justified(line))
        self._line(page, MARGIN, last)

    def _line(self, page, left: float, text: str) -> None:
        page.insert_text((left, FIRST_BASELINE + self._row * LINE_PITCH), text, fontsize=FONT_SIZE, fontname=FONT)
        self._row += 1


class TestEntryListsHoldingAFlushParagraphBrokenAfterALowercaseWordBeforeACapital(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(ParagraphBetweenEntriesPdf(Path(directory.name) / "entries.pdf").write())
        self.addCleanup(self.layer.close)

    def entries(self) -> list[str]:
        return [" ".join(entry.split()) for entry in HangingIndentList(self.layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_flush_capitalized_line_after_a_lowercase_word_filling_the_measure_continues_its_paragraph(self) -> None:
        self.assertIn(" ".join(PARAGRAPH), self.entries())

    def test_the_hanging_entries_around_the_paragraph_stay_one_entry_each(self) -> None:
        expected = entry_texts(ENTRIES_ABOVE) + [" ".join(PARAGRAPH)] + entry_texts(ENTRIES_BELOW)
        self.assertEqual(expected, self.entries())


if __name__ == "__main__":
    unittest.main()
