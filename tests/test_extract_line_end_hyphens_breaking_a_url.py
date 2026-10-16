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
URL_BROKEN_AT_A_HYPHEN = ["Reviews. https://example.org/news/one-and-", "two-essays/."]
URL_WITHOUT_A_SCHEME_BROKEN_AT_A_HYPHEN = ["see www.example.org/one-", "two."]
WORD_BROKEN_AT_A_HYPHEN = ["an exter-", "nal view"]


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


class TestLineEndHyphenBreakingAUrl(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def written(self, lines: list[str]) -> str:
        layer = TextLayer(LinesPdf(self._directory / "lines.pdf", lines).write())
        self.addCleanup(layer.close)
        return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))

    def test_a_hyphen_ending_a_line_inside_a_url_is_kept(self) -> None:
        self.assertEqual("Reviews. https://example.org/news/one-and-two-essays/.", self.written(URL_BROKEN_AT_A_HYPHEN))

    def test_a_hyphen_ending_a_line_inside_a_url_without_a_scheme_is_kept(self) -> None:
        self.assertEqual("see www.example.org/one-two.", self.written(URL_WITHOUT_A_SCHEME_BROKEN_AT_A_HYPHEN))

    def test_a_hyphen_ending_a_line_inside_a_word_is_still_dropped(self) -> None:
        self.assertEqual("an external view", self.written(WORD_BROKEN_AT_A_HYPHEN))


if __name__ == "__main__":
    unittest.main()
