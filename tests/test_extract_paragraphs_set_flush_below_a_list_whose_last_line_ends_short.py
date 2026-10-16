from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import LIST_GROUP_KIND, TEXT_KIND, Block
from _extract.indents import ParagraphIndents
from _extract.layerlines import PageLines
from _extract_fixtures import FakeLayer, RunSetting, positioned

COLUMN_LEFT = 60.0
INDENTED_LEFT = 71.0
ITEM_LEFT = 72.0
FULL_LINE = "the lead in sentence runs on as prose across the whole measure"
ITEM_ENDING_SHORT = "b) There are no reidentifiable individuals"
ITEM_FILLING_THE_MEASURE = "b) There are no distinguishable individuals in this domain at"
ROW_PITCH = 15.0
LEAD_IN_BASELINE = 20.0
ITEM_BASELINE = 60.0
FOLLOWING_BASELINE = 80.0
LEAD_IN_BOX = (0.0, 0.0, 400.0, 45.0)
ITEM_BOX = (0.0, 48.0, 400.0, 65.0)
FOLLOWING_BOX = (0.0, 68.0, 400.0, 110.0)


def two_line_paragraph(first_left: float, baseline: float, first_line_number: int) -> list:
    return (positioned(FULL_LINE, RunSetting(first_left, baseline, first_line_number))
            + positioned(FULL_LINE, RunSetting(COLUMN_LEFT, baseline + ROW_PITCH, first_line_number + 1)))


def following_paragraph_resumes(item: str) -> bool:
    chars = (two_line_paragraph(INDENTED_LEFT, LEAD_IN_BASELINE, 0)
             + positioned(item, RunSetting(ITEM_LEFT, ITEM_BASELINE, 2))
             + two_line_paragraph(COLUMN_LEFT, FOLLOWING_BASELINE, 3))
    blocks = [Block(1, TEXT_KIND, "", LEAD_IN_BOX, {}, "/page/1/Text/0"),
              Block(1, LIST_GROUP_KIND, "", ITEM_BOX, {}, "/page/1/ListGroup/1"),
              Block(1, TEXT_KIND, "", FOLLOWING_BOX, {}, "/page/1/Text/2")]
    return ParagraphIndents(PageLines(FakeLayer(chars), 1, blocks), blocks).resumes(blocks[2])


class TestParagraphsSetFlushBelowAListWhoseLastLineEndsShort(unittest.TestCase):
    def test_a_flush_paragraph_below_a_list_item_ending_short_opens_a_paragraph(self) -> None:
        self.assertFalse(following_paragraph_resumes(ITEM_ENDING_SHORT))

    def test_a_flush_paragraph_below_a_list_item_filling_the_measure_resumes_it(self) -> None:
        self.assertTrue(following_paragraph_resumes(ITEM_FILLING_THE_MEASURE))


if __name__ == "__main__":
    unittest.main()
