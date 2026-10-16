from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import HEADING_KIND, Block

HEADING_BOX = (72.0, 90.0, 400.0, 104.0)
PRINTED_HEADING = "I. The Topic: The Content and Use of Concepts"
BELL = "\x07"
ZERO_WIDTH_SPACE = "​"
EN_SPACE = " "


def heading_block(html: str) -> Block:
    return Block(1, HEADING_KIND, html, HEADING_BOX, {}, "/page/1/SectionHeader/0")


class TestHeadingLinesCarryingControlAndFormatCharacters(unittest.TestCase):
    def test_a_control_character_after_the_numeral_is_dropped_from_the_heading_text(self) -> None:
        html = f"<h2>I.{EN_SPACE} {BELL}The Topic: The Content and Use of Concepts</h2>"
        self.assertEqual(PRINTED_HEADING, heading_block(html).plain_text)

    def test_a_zero_width_space_after_the_numeral_is_dropped_from_the_heading_text(self) -> None:
        html = f"<h2>I. {ZERO_WIDTH_SPACE}The Topic: The Content and Use of Concepts</h2>"
        self.assertEqual(PRINTED_HEADING, heading_block(html).plain_text)


if __name__ == "__main__":
    unittest.main()
