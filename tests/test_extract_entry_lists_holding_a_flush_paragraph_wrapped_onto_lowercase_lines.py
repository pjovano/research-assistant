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
PARAGRAPH = ["This project by a university press, which began publishing in the",
             "seventies, will eventually amount to many volumes. Most of them are",
             "available in paperback."]
FILLS = True
RAGGED = False
ENTRIES = [(["An Essay Concerning the Understanding of Things, edited by a Scholar", "(Oxford, 1975)."], FILLS),
           (["The Correspondence, eight volumes (1976-89)."], RAGGED),
           (["A Paraphrase and Notes on the Epistles of the Apostle, two volumes,",
             "edited by another Scholar (1987)."], FILLS),
           (["Stroud, B., The Significance of Philosophical Scepticism, Oxford:", "Clarendon Press, 1984."], FILLS),
           (["Quine, W. V., Word and Object, Cambridge, Mass.: The Technology Press", "of MIT, 1960."], FILLS),
           (["Russell, B., The Autobiography, second volume, London: Allen, 1968."], FILLS),
           (["van Fraassen, B. C., The Scientific Image, Oxford: Clarendon, 1980."], RAGGED)]


def justified(line: str) -> str:
    words = line.split()
    spaces = MEASURE_CHARS - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


class ParagraphAboveEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._row = 0

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._paragraph(page)
            for lines, opening_fills in ENTRIES:
                self._entry(page, lines, opening_fills)
            document.save(self._path)
        return self._path

    def _paragraph(self, page) -> None:
        *filled, last = PARAGRAPH
        for line in filled:
            self._line(page, MARGIN, justified(line))
        self._line(page, MARGIN, last)

    def _entry(self, page, lines: list[str], opening_fills: bool) -> None:
        opening, *run_on = lines
        self._line(page, MARGIN, justified(opening) if opening_fills else opening)
        for line in run_on:
            self._line(page, MARGIN + HANGING_INDENT, line)

    def _line(self, page, left: float, text: str) -> None:
        page.insert_text((left, FIRST_BASELINE + self._row * LINE_PITCH), text, fontsize=FONT_SIZE, fontname=FONT)
        self._row += 1


class TestEntryListsHoldingAFlushParagraphWrappedOntoLowercaseLines(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(ParagraphAboveEntriesPdf(Path(directory.name) / "entries.pdf").write())
        self.addCleanup(self.layer.close)

    def entries(self) -> list[str]:
        return [" ".join(entry.split()) for entry in HangingIndentList(self.layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_flush_lowercase_line_after_a_line_filling_the_measure_continues_its_paragraph(self) -> None:
        self.assertEqual(" ".join(PARAGRAPH), self.entries()[0])

    def test_the_hanging_entries_after_the_paragraph_stay_one_entry_each(self) -> None:
        self.assertEqual([" ".join(lines) for lines, _opening_fills in ENTRIES], self.entries()[1:])


if __name__ == "__main__":
    unittest.main()
