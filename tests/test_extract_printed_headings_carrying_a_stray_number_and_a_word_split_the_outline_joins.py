from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.headings import HeadingMatch

OUTLINE_TITLE = "Metalanguage and Truth"
PRINTED_WITH_A_MARGIN_NUMBER_AND_A_SPLIT_WORD = "Meta language and 82 Truth"
PRINTED_WITH_ANOTHER_WORD = "Meta language and 82 Proof"


class TestPrintedHeadingsCarryingAStrayNumberAndAWordSplitTheOutlineJoins(unittest.TestCase):
    def test_the_printed_heading_names_the_outline_title(self) -> None:
        self.assertTrue(HeadingMatch().matches(PRINTED_WITH_A_MARGIN_NUMBER_AND_A_SPLIT_WORD, OUTLINE_TITLE))

    def test_a_printed_heading_whose_words_differ_does_not_name_the_title(self) -> None:
        self.assertFalse(HeadingMatch().matches(PRINTED_WITH_ANOTHER_WORD, OUTLINE_TITLE))


if __name__ == "__main__":
    unittest.main()
