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
MARGIN = 54.0
MEASURE_CHARS = 72
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
AUTHOR_LED = 0
YEAR_LED = 2
RUN_ON = 4
QUOTED = 8
EXPANSION = 9
KEYED_RUN_ON = 11
FILLS = True
ENDS_SHORT = False
YEAR_LED_ENTRIES = [
    [(AUTHOR_LED, "Adorno, Theodor. 1997. Aesthetic Theory. Translated by Robert", FILLS),
     (RUN_ON, "Hullot-Kentor. Minneapolis: University Press.", ENDS_SHORT)],
    [(AUTHOR_LED, "Beiser, Frederick. 1992. Enlightenment, Revolution, and Romanticism.", FILLS),
     (RUN_ON, "Cambridge, MA: Harvard University Press.", ENDS_SHORT)],
    [(YEAR_LED, "2003. Hegel and Naturphilosophie. Studies in History and Philosophy", FILLS),
     (RUN_ON, "of Science 34(1): 135-37.", ENDS_SHORT)],
    [(YEAR_LED, "2005. Schiller as a Philosopher. Oxford: Clarendon Press.", ENDS_SHORT)],
    [(YEAR_LED, "2006. Kant and Naturphilosophie. In The Kantian Legacy in Nineteenth", FILLS),
     (RUN_ON, "Century Science, edited by Michael Friedman and Alfred Nordman,", FILLS),
     (RUN_ON, "7-26. Cambridge, MA: MIT Press.", ENDS_SHORT)],
    [(AUTHOR_LED, "Bell, John L. 2019. The Continuous, the Discrete and the Infinitesimal", FILLS),
     (RUN_ON, "in Philosophy and Mathematics. Berlin: Springer.", ENDS_SHORT)]]
QUOTING_NOTES = [
    [(AUTHOR_LED, "55 Williams, Persons, Character, Morality, in Moral Luck, p. 18.", ENDS_SHORT)],
    [(AUTHOR_LED, "56 The same phenomenon can be seen in sports. The critic points it out", FILLS),
     (RUN_ON, "in commenting on a champion:", ENDS_SHORT),
     (QUOTED, "For promising junior players, refining the kinesthetic sense is", FILLS),
     (QUOTED, "the main goal of the extreme daily practice regimens we often", FILLS),
     (QUOTED, "hear about. The training here is both muscular and neurological.", FILLS),
     (QUOTED, "Hitting thousands of strokes, day after day, builds the ability", FILLS),
     (QUOTED, "to do by feel what cannot be done by regular conscious thought.", ENDS_SHORT)],
    [(AUTHOR_LED, "57 McDowell, Response to Dreyfus, p. 369.", ENDS_SHORT)],
    [(AUTHOR_LED, "58 Not to say, in this type of situation always do this type of thing,", FILLS),
     (RUN_ON, "since that only pushes off the question.", ENDS_SHORT)]]

KEYED_ENTRIES = [
    [(AUTHOR_LED, "Ak", ENDS_SHORT), (EXPANSION, "Kants Gesammelte Schriften, 29 vols. Berlin: Reimer,", FILLS),
     (KEYED_RUN_ON, "now De Gruyter, 1902-.", ENDS_SHORT)],
    [(AUTHOR_LED, "CPR", ENDS_SHORT), (EXPANSION, "Kritik der reinen Vernunft: 1st ed., 1781 (A), Ak 4;", FILLS),
     (KEYED_RUN_ON, "2nd ed., 1787 (B), Ak 3.", ENDS_SHORT)]]
SAME_ROW = {EXPANSION}


def justified(line: str, measure_chars: int) -> str:
    words = line.split()
    spaces = measure_chars - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


class IndentedEntriesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, entries: list[list[tuple[int, str, bool]]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            row = -1
            for indent_chars, text, fills in (line for entry in entries for line in entry):
                row += 0 if indent_chars in SAME_ROW else 1
                printed = justified(text, MEASURE_CHARS - indent_chars) if fills else text
                page.insert_text((MARGIN + indent_chars * CHAR_WIDTH, FIRST_BASELINE + row * LINE_PITCH), printed,
                                 fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def entry_texts(entries: list[list[tuple[int, str, bool]]]) -> list[str]:
    return [" ".join(text for _indent, text, _fills in entry) for entry in entries]


class TestEntryListsOpeningAnAuthorsLaterEntriesOnTheirYear(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "entries.pdf"

    def entries(self, printed: list[list[tuple[int, str, bool]]]) -> list[str]:
        layer = TextLayer(IndentedEntriesPdf(self._path).write(printed))
        self.addCleanup(layer.close)
        return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_line_opening_short_of_the_run_on_indent_after_an_entry_ends_opens_an_entry(self) -> None:
        self.assertEqual(entry_texts(YEAR_LED_ENTRIES), self.entries(YEAR_LED_ENTRIES))

    def test_a_line_short_of_a_quotations_indent_after_a_line_filling_the_measure_runs_on(self) -> None:
        self.assertEqual(entry_texts(QUOTING_NOTES), self.entries(QUOTING_NOTES))

    def test_a_line_set_on_the_row_of_the_line_before_runs_on(self) -> None:
        self.assertEqual(entry_texts(KEYED_ENTRIES), self.entries(KEYED_ENTRIES))


if __name__ == "__main__":
    unittest.main()
