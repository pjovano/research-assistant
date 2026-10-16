from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnote_marks_read_as_the_closing_superscript_of_a_formula import FormulaMarkCase
from _extract.sentences import breaks_off_mid_sentence

NOTE = "Clearly, the premise is the negation."
DISPLAYED_READING = r'<math display="block">\Phi \text{ is a prime filter}^{19} \text{ in } H.</math>'
DISPLAYED_WITH_ITS_MARK = r"$$\Phi \text{ is a prime filter} \text{ in } H.$$[^19]"
INLINE_READING = r"3 <math>\Phi \text{ is prime}^19 \wedge x</math> holds."
INLINE_WITH_ITS_MARK = r"3 $\Phi \text{ is prime} \wedge x$[^19] holds."
SYMBOL_EXPONENT_READING = r"4 <math>x^{19} + y</math>"


class TestFootnoteMarksRaisedOnTheWordsInsideAFormula(FormulaMarkCase):
    def test_a_numeral_raised_on_a_displayed_formulas_words_becomes_a_mark_set_after_the_formula(self) -> None:
        paragraphs, _definitions = self.written(DISPLAYED_READING)
        self.assertEqual([DISPLAYED_WITH_ITS_MARK], paragraphs)

    def test_a_numeral_raised_on_an_inline_formulas_words_becomes_a_mark_set_after_the_formula(self) -> None:
        paragraphs, _definitions = self.written(INLINE_READING)
        self.assertEqual([INLINE_WITH_ITS_MARK], paragraphs)

    def test_the_note_takes_its_printed_numeral(self) -> None:
        _paragraphs, definitions = self.written(DISPLAYED_READING)
        self.assertEqual([(19, NOTE)], definitions)

    def test_a_numeral_raised_on_a_symbol_inside_the_formula_stays_in_the_formula(self) -> None:
        paragraphs, _definitions = self.written(SYMBOL_EXPONENT_READING)
        self.assertEqual([r"4 $x^{19} + y$"], paragraphs)

    def test_a_displayed_formula_ending_on_its_mark_breaks_off_mid_sentence(self) -> None:
        self.assertTrue(breaks_off_mid_sentence(DISPLAYED_WITH_ITS_MARK))

    def test_a_sentence_closed_before_its_mark_does_not_break_off(self) -> None:
        self.assertFalse(breaks_off_mid_sentence("The premise is the negation.[^19]"))


if __name__ == "__main__":
    unittest.main()
