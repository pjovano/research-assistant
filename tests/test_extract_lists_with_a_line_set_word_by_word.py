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
TALLER_FONT_SIZE = 10.5
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
MARGIN = 63.0
NOTE_NUMBER_LEFT = 78.0
MEASURE_CHARS = 64
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
FIRST_NOTE = ["1  The  first  note  opens with its number and runs on across",
              "several  lines  of  prose set flush with the margin of the page,",
              "each line filling the measure from the margin to the right edge,",
              "so  that  the note reads as justified prose, before it ends here",
              "at last with a short line."]
SECOND_NOTE_OPENING = ["2 This", "bi-dimensional", "account", "of", "content,", "given", "in", "terms"]
SECOND_NOTE_RUN_ON = ["consequences  of  application, extends to descriptive vocabulary",
                      "the  inferential treatment of logical vocabulary by introduction",
                      "and  elimination  rules  in  natural  deduction, see the closing",
                      "note."]
THIRD_NOTE = ["3  The  third note follows on its own line and runs on across",
              "the  measure  to  a second and a third line of prose, which fill",
              "it, and then ends."]


class WordByWordNotesPdf:
    def __init__(self, path: Path, taller_word: str | None) -> None:
        self._path = path
        self._taller_word = taller_word
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            self._note(page, FIRST_NOTE)
            self._words(page, SECOND_NOTE_OPENING)
            self._run_on(page, SECOND_NOTE_RUN_ON)
            self._note(page, THIRD_NOTE)
            document.save(self._path)
        return self._path

    def _note(self, page, lines: list[str]) -> None:
        opening, *run_on = lines
        self._line(page, NOTE_NUMBER_LEFT, opening)
        self._run_on(page, run_on)

    def _run_on(self, page, lines: list[str]) -> None:
        for line in lines:
            self._line(page, MARGIN, line)

    def _words(self, page, words: list[str]) -> None:
        left = NOTE_NUMBER_LEFT
        word_space = self._justified_space(words)
        for word in words:
            page.insert_text((left, self._baseline), word, fontsize=self._size_of(word), fontname=FONT)
            left += pymupdf.get_text_length(word, FONT, self._size_of(word)) + word_space
        self._baseline += LINE_PITCH

    def _size_of(self, word: str) -> float:
        return TALLER_FONT_SIZE if word == self._taller_word else FONT_SIZE

    def _justified_space(self, words: list[str]) -> float:
        measure_right = MARGIN + pymupdf.get_text_length("x" * MEASURE_CHARS, FONT, FONT_SIZE)
        inked = sum(pymupdf.get_text_length(word, FONT, self._size_of(word)) for word in words)
        return (measure_right - NOTE_NUMBER_LEFT - inked) / (len(words) - 1)

    def _line(self, page, left: float, text: str) -> None:
        page.insert_text((left, self._baseline), text, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH


class TestNotesWithALineSetWordByWord(unittest.TestCase):
    TALLER_WORD: str | None = None

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(WordByWordNotesPdf(Path(directory.name) / "notes.pdf", self.TALLER_WORD).write())
        self.addCleanup(layer.close)
        self.entries = [" ".join(entry.split()) for entry in HangingIndentList(layer).entries(1, WHOLE_PAGE)]

    def test_the_words_of_one_line_stay_in_the_note_they_open(self) -> None:
        expected = " ".join(" ".join(SECOND_NOTE_OPENING + SECOND_NOTE_RUN_ON).split())
        self.assertEqual(expected, self.entries[1])

    def test_the_words_of_one_line_are_not_read_as_a_second_column(self) -> None:
        self.assertEqual(["1", "2", "3"], [entry.split()[0] for entry in self.entries])


class TestNotesWithALineSetWordByWordWhoseTallerWordTheLayerListsFirst(TestNotesWithALineSetWordByWord):
    TALLER_WORD = "content,"


if __name__ == "__main__":
    unittest.main()
