from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import TextLayer

FONT = "cour"
FONT_SIZE = 9.0
ADVANCE = pymupdf.get_text_length("x", FONT, FONT_SIZE)
MARGIN = 72.0
INDENT = 4 * ADVANCE
RULE_WIDTH = 20.0
RULE_GAP = 2.0
RULE_THICKNESS = 0.45
RULE_RISE_SHARE = 0.35
COVER_OVERHANG = 3.0
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
GREY = (0.58, 0.58, 0.6)
WHITE = (1.0, 1.0, 1.0)
DASH = "—"
HIDDEN_RULE_BASELINE = 100.0
SHOWN_RULE_BASELINE = 140.0
HIDDEN_RULE_LINE = "The opening of a paragraph beside a hidden rule."
SHOWN_RULE_LINE = "The opening of a paragraph beside a shown rule."


class GutterRulesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            self._ruled_line(page, HIDDEN_RULE_BASELINE, HIDDEN_RULE_LINE)
            self._cover(page, self._rule(HIDDEN_RULE_BASELINE))
            self._ruled_line(page, SHOWN_RULE_BASELINE, SHOWN_RULE_LINE)
            document.save(self._path)
        return self._path

    def _ruled_line(self, page, baseline: float, text: str) -> None:
        rule = self._rule(baseline)
        page.draw_rect(rule, color=None, fill=GREY)
        page.draw_rect(rule, color=GREY, fill=None, width=0)
        page.insert_text((rule.x1 + RULE_GAP, baseline), text, fontsize=FONT_SIZE, fontname=FONT)

    @staticmethod
    def _rule(baseline: float) -> pymupdf.Rect:
        left = MARGIN + INDENT - RULE_GAP - RULE_WIDTH
        top = baseline - RULE_RISE_SHARE * FONT_SIZE - RULE_THICKNESS / 2
        return pymupdf.Rect(left, top, left + RULE_WIDTH, top + RULE_THICKNESS)

    @staticmethod
    def _cover(page, rule: pymupdf.Rect) -> None:
        cover = pymupdf.Rect(rule.x0 - COVER_OVERHANG, rule.y0 - COVER_OVERHANG,
                             rule.x1 + COVER_OVERHANG, rule.y1 + COVER_OVERHANG)
        page.draw_rect(cover, color=None, fill=WHITE)


class TestRulesPaintedOverByALaterOpaqueFill(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(GutterRulesPdf(Path(directory.name) / "gutter.pdf").write())
        self.addCleanup(self.layer.close)

    def line_text(self, opening: str) -> str:
        texts = [line.text for line in self.layer.lines_in(1, WHOLE_PAGE)]
        return next(text for text in texts if opening in text)

    def test_a_rule_painted_over_by_a_later_opaque_fill_does_not_read_as_a_dash(self) -> None:
        self.assertEqual(HIDDEN_RULE_LINE, self.line_text(HIDDEN_RULE_LINE).strip())

    def test_a_rule_left_uncovered_still_reads_as_a_dash(self) -> None:
        self.assertIn(DASH, self.line_text(SHOWN_RULE_LINE))


if __name__ == "__main__":
    unittest.main()
