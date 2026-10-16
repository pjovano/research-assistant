from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _annotate.pages import VisualLine
from _annotate.spans import WordBox


def line_ending_in(word: str) -> VisualLine:
    return VisualLine((WordBox(0, 0.0, 0.0, 10.0, 10.0, "Prose"), WordBox(1, 20.0, 0.0, 30.0, 10.0, word)))


class TestALineEdgeCarriesAFolioOnlyAsAWellFormedNumeral(unittest.TestCase):
    def test_a_well_formed_roman_numeral_at_the_edge_is_a_folio(self) -> None:
        self.assertTrue(line_ending_in("xiv").carries_folio)

    def test_a_word_of_roman_letters_that_is_no_well_formed_numeral_is_not_a_folio(self) -> None:
        for word in ("did", "mill", "civil"):
            with self.subTest(word=word):
                self.assertFalse(line_ending_in(word).carries_folio)


if __name__ == "__main__":
    unittest.main()
