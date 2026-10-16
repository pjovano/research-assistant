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
FIRST_BASELINE = 100.0
MARGIN = 63.0
MEASURE_CHARS = 70
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 660.0
WHOLE_PAGE = Box(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT)
FLUSH, REPEATED_AUTHOR_INDENT, RUN_ON_INDENT = 0, 1, 2
FILLS, RAGGED = True, False
ENTRY_ENDING_SHORT = [
    (FLUSH, FILLS, "Kant, Immanuel. Kritik der reinen Vernunft. Edited by Raymund Schmidt."),
    (RUN_ON_INDENT, RAGGED, "Hamburg: Felix Meiner Verlag, 1990."),
]
PARAGRAPH_AFTER_A_SHORT_LINE = [
    (RUN_ON_INDENT, FILLS, "Another valuable edition of the first Critique, also including the"),
    (FLUSH, FILLS, "Prolegomena and drafts for the essay What is the Real Progress that"),
    (FLUSH, RAGGED, "Metaphysics has made in Germany, is:"),
]
ENTRY_ENDING_AT_THE_MEASURE = [
    (FLUSH, FILLS, "Kant, Immanuel. Theoretische Philosophie: Texte und Kommentar. Edited"),
    (RUN_ON_INDENT, FILLS, "by Georg Mohr. Three volumes. Frankfurt am Main: Suhrkamp, 2004."),
]
PARAGRAPH_AFTER_A_FULL_STOP_AT_THE_MEASURE = [
    (RUN_ON_INDENT, FILLS, "The following volumes in the series Kant-Forschungen, begun by"),
    (FLUSH, FILLS, "Reinhard Brandt, revise or add newly found material. These include:"),
]
ENTRY_AFTER_A_COLON_AT_THE_MEASURE = [
    (FLUSH, FILLS, "Brandt, Reinhard and Werner Stark, eds. Neue Autographen und Dokumente"),
    (RUN_ON_INDENT, RAGGED, "zu Kants Leben. Hamburg: Felix Meiner Verlag, 1987."),
]
PIECES = [ENTRY_ENDING_SHORT, PARAGRAPH_AFTER_A_SHORT_LINE, ENTRY_ENDING_AT_THE_MEASURE,
          PARAGRAPH_AFTER_A_FULL_STOP_AT_THE_MEASURE, ENTRY_AFTER_A_COLON_AT_THE_MEASURE]
UNPUNCTUATED_PIECES = [
    [(FLUSH, FILLS, "Pinkard, Terry (1994) Hegel's Phenomenology: The Sociality of Reason"),
     (RUN_ON_INDENT, RAGGED, "Cambridge: Cambridge University Press")],
    [(REPEATED_AUTHOR_INDENT, FILLS, "(2002) German Philosophy 1760-1860 Cambridge: Cambridge University")],
    [(FLUSH, FILLS, "Pippin, Robert (1989) Hegel's Idealism: The Satisfactions of Self"),
     (RUN_ON_INDENT, RAGGED, "Consciousness Cambridge: Cambridge University Press")],
]


def justified(line: str, width: int) -> str:
    words = line.split()
    spaces = width - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * gap_width for word, gap_width in zip(words, widths + [0]))


def piece_text(piece: list[tuple[int, bool, str]]) -> str:
    return " ".join(text for _indent, _fills, text in piece)


class IndentedParagraphsAmongEntriesPdf:
    def __init__(self, path: Path, pieces: list[list[tuple[int, bool, str]]]) -> None:
        self._path = path
        self._pieces = pieces
        self._row = 0

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for piece in self._pieces:
                for line in piece:
                    self._line(page, line)
            document.save(self._path)
        return self._path

    def _line(self, page, line: tuple[int, bool, str]) -> None:
        indent, fills, text = line
        set_text = justified(text, MEASURE_CHARS - indent) if fills else text
        origin = (MARGIN + indent * CHAR_WIDTH, FIRST_BASELINE + self._row * LINE_PITCH)
        page.insert_text(origin, set_text, fontsize=FONT_SIZE, fontname=FONT)
        self._row += 1


class TestEntryListsHoldingAParagraphSetWithAFirstLineIndent(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def entries(self, pieces: list[list[tuple[int, bool, str]]] = PIECES) -> list[str]:
        layer = TextLayer(IndentedParagraphsAmongEntriesPdf(self._directory / "entries.pdf", pieces).write())
        self.addCleanup(layer.close)
        return [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(FILE_PAGE, WHOLE_PAGE)]

    def test_a_paragraph_indented_below_a_line_ending_short_opens_apart_from_the_entry_above(self) -> None:
        self.assertEqual(piece_text(ENTRY_ENDING_SHORT), self.entries()[0])

    def test_flush_lines_continue_the_indented_paragraph_while_its_lines_run_on_mid_sentence(self) -> None:
        self.assertEqual(piece_text(PARAGRAPH_AFTER_A_SHORT_LINE), self.entries()[1])

    def test_a_paragraph_indented_below_a_full_stop_at_the_measure_opens_apart_from_the_entry_above(self) -> None:
        expected = [piece_text(ENTRY_ENDING_AT_THE_MEASURE), piece_text(PARAGRAPH_AFTER_A_FULL_STOP_AT_THE_MEASURE)]
        self.assertEqual(expected, self.entries()[2:4])

    def test_an_entry_below_a_paragraph_ending_on_a_colon_at_the_measure_opens_apart_from_it(self) -> None:
        self.assertEqual(piece_text(ENTRY_AFTER_A_COLON_AT_THE_MEASURE), self.entries()[4])

    def test_each_piece_is_one_entry(self) -> None:
        self.assertEqual(len(PIECES), len(self.entries()))

    def test_an_indented_line_running_on_into_a_flush_one_opens_no_paragraph_where_entries_end_unpunctuated(
            self) -> None:
        self.assertEqual([piece_text(piece) for piece in UNPUNCTUATED_PIECES], self.entries(UNPUNCTUATED_PIECES))


if __name__ == "__main__":
    unittest.main()
