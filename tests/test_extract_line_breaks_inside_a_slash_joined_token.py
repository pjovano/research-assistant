from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of

WHOLE_PAGE = Box(0.0, 0.0, 1000.0, 1000.0)
FIRST_BASELINE = 100.0
LINE_PITCH = 14.0
LEFT_MARGIN = 72.0
FONT_SIZE = 11.0
URL_BROKEN_INSIDE_A_PATH_WORD = ["Encyclopedia, https://example.org/archives/su", "m2018/entries/hegel (accessed)."]
URL_BROKEN_INSIDE_A_PATH_NUMBER = ["Quarterly, http://example.org/article/view/38", "68/3407 (accessed)."]
URL_BROKEN_AFTER_A_HOST_WITHOUT_A_SCHEME = ["see www.example.org", "/archives/2018 for the text."]
RANGE_BROKEN_AFTER_ITS_SLASH = ["Lectures, Berlin 1825/", "26. Hamburg: Meiner."]
WORDS_BROKEN_AFTER_THEIR_SLASH = ["the sense and/", "or the reference."]
VERSE_LINES_PARTED_BY_A_SPACED_SLASH = ["Shall I compare thee /", "to a summer's day?"]
COMPLETE_URL_BEFORE_A_WORD = ["see https://example.org/archives", "for the text."]
COMPLETE_URL_ENDING_IN_A_SLASH_BEFORE_A_PARENTHESIS = ["see https://example.org/", "(accessed)."]


class LinesPdf:
    def __init__(self, path: Path, lines: list[str]) -> None:
        self._path = path
        self._lines = lines

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, line in enumerate(self._lines):
                page.insert_text((LEFT_MARGIN, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


class LineBreakCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def written(self, lines: list[str]) -> str:
        layer = TextLayer(LinesPdf(self._directory / "lines.pdf", lines).write())
        self.addCleanup(layer.close)
        return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))


class TestLineBreakInsideAUrl(LineBreakCase):
    def test_a_url_broken_inside_a_word_of_its_path_joins_without_a_space(self) -> None:
        self.assertEqual("Encyclopedia, https://example.org/archives/sum2018/entries/hegel (accessed).",
                         self.written(URL_BROKEN_INSIDE_A_PATH_WORD))

    def test_a_url_broken_inside_a_number_of_its_path_joins_without_a_space(self) -> None:
        self.assertEqual("Quarterly, http://example.org/article/view/3868/3407 (accessed).",
                         self.written(URL_BROKEN_INSIDE_A_PATH_NUMBER))

    def test_a_url_without_a_scheme_broken_before_its_path_joins_without_a_space(self) -> None:
        self.assertEqual("see www.example.org/archives/2018 for the text.",
                         self.written(URL_BROKEN_AFTER_A_HOST_WITHOUT_A_SCHEME))

    def test_a_url_ending_a_line_before_a_word_keeps_the_space(self) -> None:
        self.assertEqual("see https://example.org/archives for the text.", self.written(COMPLETE_URL_BEFORE_A_WORD))

    def test_a_url_ending_in_a_slash_before_a_parenthesis_keeps_the_space(self) -> None:
        self.assertEqual("see https://example.org/ (accessed).",
                         self.written(COMPLETE_URL_ENDING_IN_A_SLASH_BEFORE_A_PARENTHESIS))


class TestLineBreakAfterASlash(LineBreakCase):
    def test_a_year_range_broken_after_its_slash_joins_without_a_space(self) -> None:
        self.assertEqual("Lectures, Berlin 1825/26. Hamburg: Meiner.", self.written(RANGE_BROKEN_AFTER_ITS_SLASH))

    def test_words_broken_after_their_slash_join_without_a_space(self) -> None:
        self.assertEqual("the sense and/or the reference.", self.written(WORDS_BROKEN_AFTER_THEIR_SLASH))

    def test_a_slash_set_apart_from_the_word_before_it_keeps_the_space(self) -> None:
        self.assertEqual("Shall I compare thee / to a summer's day?",
                         self.written(VERSE_LINES_PARTED_BY_A_SPACED_SLASH))


if __name__ == "__main__":
    unittest.main()
