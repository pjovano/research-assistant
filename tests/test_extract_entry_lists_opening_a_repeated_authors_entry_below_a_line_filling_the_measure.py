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
MEASURE_CHARS = 72
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
AUTHOR_LED = 0
REPEATED_AUTHOR = 2
RUN_ON = 4
FILLS = True
ENDS_SHORT = False
REPEATED_AUTHOR_ENTRIES = [
    [(AUTHOR_LED, "Adams, Anna (1971). Hegel im Kontext. Frankfurt am Main: Suhrkamp Verlag", FILLS)],
    [(REPEATED_AUTHOR, "ed. (1978). Die Wissenschaft der Logik und die Logik der Reflexion.", FILLS),
     (RUN_ON, "Bonn: Bouvier", ENDS_SHORT)],
    [(AUTHOR_LED, "Baker, Bernd, ed. (1978). Seminar: Dialektik in der Philosophie Hegels.", FILLS),
     (RUN_ON, "Frankfurt am Main: Suhrkamp Verlag", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "(1984). Ontologie und Relationen: Hegel, Bradley, Russell und die", FILLS),
     (RUN_ON, "Kontroverse über interne und externe Beziehungen. Hain", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "(1991). Die Grenzen der Vernunft. Frankfurt am Main: Hain", ENDS_SHORT)],
    [(AUTHOR_LED, "Carter, Clara (2004). Hegel und die Philosophie der Natur. Stuttgart:", FILLS),
     (RUN_ON, "Klett-Cotta", ENDS_SHORT)]]
ENTRIES_CLOSING_ON_A_FULL_LINE = [
    [(AUTHOR_LED, "Adams, Anna, Hegel im Kontext. Die Logik der Reflexion und ihre Quellen", FILLS),
     (RUN_ON, "und Wirkungen (Frankfurt am Main: Suhrkamp, 1971). Second edition.", FILLS)],
    [(REPEATED_AUTHOR, "(ed.), Die Wissenschaft der Logik und die Logik der Reflexion. Mit", FILLS),
     (RUN_ON, "Beitraegen (Bonn: Bouvier, 1978).", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "Die Grenzen der Vernunft (Frankfurt am Main: Hain, 1991).", ENDS_SHORT)]]
QUOTING_NOTES = [
    [(AUTHOR_LED, "56 The same phenomenon can be seen in sports. The critic points it out", FILLS),
     (REPEATED_AUTHOR, "in commenting on a champion:", ENDS_SHORT),
     (RUN_ON, "For promising junior players, refining the kinesthetic sense is", FILLS),
     (RUN_ON, "the main goal of the extreme daily practice regimens we often", FILLS),
     (RUN_ON, "hear about. The training here is both muscular and neurological.", ENDS_SHORT)],
    [(AUTHOR_LED, "57 Not to say, in this type of situation always do this type of thing,", FILLS),
     (REPEATED_AUTHOR, "since that only pushes off the question.", ENDS_SHORT)]]


def justified(line: str, measure_chars: int) -> str:
    words = line.split()
    spaces = measure_chars - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


class ThreeIndentEntriesPdf:
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


class TestEntryListsOpeningARepeatedAuthorsEntryBelowALineFillingTheMeasure(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "entries.pdf"

    def entries(self, printed: list[list[tuple[int, str, bool]]]) -> list[str]:
        layer = TextLayer(ThreeIndentEntriesPdf(self._path).write(printed))
        self.addCleanup(layer.close)
        return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_line_at_the_indent_entries_open_at_opens_an_entry_below_a_line_filling_the_measure(self) -> None:
        self.assertEqual(entry_texts(REPEATED_AUTHOR_ENTRIES), self.entries(REPEATED_AUTHOR_ENTRIES))

    def test_a_line_at_the_indent_entries_open_at_opens_an_entry_below_a_full_line_closing_on_a_full_stop(
            self) -> None:
        self.assertEqual(entry_texts(ENTRIES_CLOSING_ON_A_FULL_LINE), self.entries(ENTRIES_CLOSING_ON_A_FULL_LINE))

    def test_a_line_at_an_indent_only_run_on_lines_take_runs_on_below_a_line_filling_the_measure(self) -> None:
        self.assertEqual(entry_texts(QUOTING_NOTES), self.entries(QUOTING_NOTES))


if __name__ == "__main__":
    unittest.main()
