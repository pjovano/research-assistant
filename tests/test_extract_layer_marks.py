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
from _layer_pdfs import RemappedTextPdf, StandIn

WHOLE_PAGE = Box(0.0, 0.0, 1000.0, 1000.0)
LEFT = 72.0
FIRST_BASELINE = 100.0
PITCH = 12.0
BODY = 10.5
MARK = 6.0
MARK_RISE = 5.0
COMBINING_DIAERESIS = StandIn("̈", zero_width=True)
SOFT_HYPHEN = StandIn("­", zero_width=True)


class LayerMarksCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def written(self, lines: list[str], stand_ins: dict[str, StandIn]) -> str:
        layer = TextLayer(RemappedTextPdf(self._directory / "marks.pdf", lines, stand_ins).write())
        self.addCleanup(layer.close)
        return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))


class TestCombiningMarks(LayerMarksCase):
    def test_a_zero_width_combining_mark_composes_with_the_letter_before_it(self) -> None:
        self.assertEqual("the Jäsche Logic", self.written(["the Ja^sche Logic"], {"^": COMBINING_DIAERESIS}))


class TestSoftHyphens(LayerMarksCase):
    def test_a_soft_hyphen_inside_a_line_is_dropped(self) -> None:
        self.assertEqual("a quasi-transcendental reading of chapter six",
                         self.written(["a quasi-~transcendental reading of ~chapter six"], {"~": SOFT_HYPHEN}))

    def test_a_soft_hyphen_ending_a_line_breaks_the_word_across_the_lines(self) -> None:
        self.assertEqual("the whole hyphenation rule",
                         self.written(["the whole hyphen~", "ation rule"], {"~": SOFT_HYPHEN}))

    def test_a_soft_hyphen_after_a_hard_hyphen_leaves_the_hard_hyphen_to_the_join(self) -> None:
        self.assertEqual("of sense-certainty, as sense-certainty",
                         self.written(["of sense-certainty, as sense-~", "certainty"], {"~": SOFT_HYPHEN}))


class TestNoteMarkSetOnItsOwnLine(unittest.TestCase):
    def test_a_small_mark_set_on_its_own_line_above_a_row_is_raised_at_the_end_of_that_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mark.pdf"
            with pymupdf.open() as document:
                page = document.new_page()
                page.insert_text((LEFT, FIRST_BASELINE), "the aim is always connected", fontname="helv", fontsize=BODY)
                second = "with the feeling (CJ 27)."
                page.insert_text((LEFT, FIRST_BASELINE + PITCH), second, fontname="helv", fontsize=BODY)
                mark_left = LEFT + pymupdf.get_text_length(second, fontname="helv", fontsize=BODY) + 1.0
                page.insert_text((mark_left, FIRST_BASELINE + PITCH - MARK_RISE), "3", fontname="helv", fontsize=MARK)
                document.save(path)
            layer = TextLayer(path)
            written = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
            layer.close()
        self.assertEqual("the aim is always connected with the feeling (CJ 27).<sup>3</sup>", written)


if __name__ == "__main__":
    unittest.main()
