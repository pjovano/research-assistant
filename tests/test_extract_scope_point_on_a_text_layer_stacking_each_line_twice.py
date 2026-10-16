from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf

from _extract.layer import TextLayer
from _extract.spans import PagePlace, ScopePoints, UnresolvedScopePoint

LINES = ('"The world," said someone, "is all that is the case."', "According to the theory, the truth",
         "is the totality of assertions.", "According to the theory, the truth")
FIRST_BASELINE, PITCH = 100.0, 40.0
LEFT_MARGIN = 72
STACKED_OFFSET = 0.8
INVISIBLE = 3
RESUMED_ROW = 0
EXCLUDED_ROW = 2


def stacked_pdf(path: Path) -> Path:
    with pymupdf.open() as document:
        page = document.new_page()
        for row, text in enumerate(LINES):
            baseline = FIRST_BASELINE + row * PITCH
            page.insert_text((LEFT_MARGIN, baseline), text, render_mode=INVISIBLE)
            page.insert_text((LEFT_MARGIN + STACKED_OFFSET, baseline + STACKED_OFFSET), text, render_mode=INVISIBLE)
        document.save(path)
    return path


class TestAScopePointOnATextLayerStackingEachLineTwice(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        self.points = ScopePoints(TextLayer(stacked_pdf(directory / "stacked.pdf")))

    def place(self, row: int) -> PagePlace:
        return PagePlace(1, FIRST_BASELINE + row * PITCH)

    def test_a_point_quoting_a_stacked_line_names_its_one_place(self) -> None:
        spans = self.points.spans([("1", '1: "The world," said someone')])
        self.assertFalse(spans.excludes(self.place(RESUMED_ROW)))

    def test_a_point_quoting_a_whole_stacked_line_names_its_one_place(self) -> None:
        spans = self.points.spans([("1: is the totality of assertions.", "end")])
        self.assertTrue(spans.excludes(self.place(EXCLUDED_ROW)))

    def test_a_point_opening_stacked_lines_at_two_places_is_refused(self) -> None:
        with self.assertRaises(UnresolvedScopePoint):
            self.points.spans([("1: According to the theory", "end")])

    def test_the_refusal_asks_for_more_of_the_lines_words(self) -> None:
        with self.assertRaisesRegex(UnresolvedScopePoint, "quote more of the line's words"):
            self.points.spans([("1: According to the theory", "end")])


if __name__ == "__main__":
    unittest.main()
