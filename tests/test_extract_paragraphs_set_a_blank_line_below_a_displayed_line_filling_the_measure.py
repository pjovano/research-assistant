from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block
from _extract.indents import ParagraphIndents
from _extract.layerlines import PageLines
from _extract_fixtures import FakeLayer, RunSetting, positioned

COLUMN_LEFT = 60.0
INDENTED_LEFT = 71.0
FULL_LINE = "the lead in sentence runs on as prose across the whole measure"
DISPLAYED_LINE = "H(b): There are no strictly distinguishable objects in it at all,"
ROW_PITCH = 15.0
LEAD_IN_BASELINE = 20.0
DISPLAYED_BASELINE = 60.0
NEXT_LINE = DISPLAYED_BASELINE + ROW_PITCH
A_BLANK_LINE_BELOW = DISPLAYED_BASELINE + 2 * ROW_PITCH + 6.0


def two_line_paragraph(first_left: float, baseline: float, first_line_number: int) -> list:
    return (positioned(FULL_LINE, RunSetting(first_left, baseline, first_line_number))
            + positioned(FULL_LINE, RunSetting(COLUMN_LEFT, baseline + ROW_PITCH, first_line_number + 1)))


def _box(top_baseline: float, rows: int) -> tuple:
    return (0.0, top_baseline - ROW_PITCH + 2.0, 400.0, top_baseline + (rows - 1) * ROW_PITCH + 4.0)


def following_paragraph_resumes(following_baseline: float) -> bool:
    chars = (two_line_paragraph(INDENTED_LEFT, LEAD_IN_BASELINE, 0)
             + positioned(DISPLAYED_LINE, RunSetting(COLUMN_LEFT, DISPLAYED_BASELINE, 2))
             + two_line_paragraph(COLUMN_LEFT, following_baseline, 3))
    blocks = [Block(1, TEXT_KIND, "", _box(LEAD_IN_BASELINE, 2), {}, "/page/1/Text/0"),
              Block(1, TEXT_KIND, "", _box(DISPLAYED_BASELINE, 1), {}, "/page/1/Text/1"),
              Block(1, TEXT_KIND, "", _box(following_baseline, 2), {}, "/page/1/Text/2")]
    return ParagraphIndents(PageLines(FakeLayer(chars), 1, blocks), blocks).resumes(blocks[2])


class TestParagraphsSetABlankLineBelowADisplayedLineFillingTheMeasure(unittest.TestCase):
    def test_a_flush_paragraph_a_blank_line_below_opens_a_paragraph(self) -> None:
        self.assertFalse(following_paragraph_resumes(A_BLANK_LINE_BELOW))

    def test_a_flush_paragraph_on_the_next_line_resumes_the_line_above(self) -> None:
        self.assertTrue(following_paragraph_resumes(NEXT_LINE))


if __name__ == "__main__":
    unittest.main()
