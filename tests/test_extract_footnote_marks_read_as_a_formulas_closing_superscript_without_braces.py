from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnote_marks_read_as_the_closing_superscript_of_a_formula import FormulaMarkCase

NOTE = "Clearly, the premise is the negation."
FORMULA_READING = r"3 <math>\exists^19</math>"
FORMULA_WITH_ITS_MARK = r"3 $\exists$[^19]"
LONGER_EXPONENT_READING = r"4 <math>x^219</math>"
DISPLAYED_FORMULA_READING = r'<math display="block">R^M = R^N.^19</math>'
DISPLAYED_FORMULA_WITH_ITS_MARK = r"$$R^M = R^N.$$[^19]"


class TestFootnoteMarksReadAsAFormulasClosingSuperscriptWithoutBraces(FormulaMarkCase):
    def test_the_formulas_closing_superscript_without_braces_becomes_the_mark_of_the_note_printing_that_numeral(
            self) -> None:
        paragraphs, _definitions = self.written(FORMULA_READING)
        self.assertEqual([FORMULA_WITH_ITS_MARK], paragraphs)

    def test_the_note_takes_its_printed_numeral(self) -> None:
        _paragraphs, definitions = self.written(FORMULA_READING)
        self.assertEqual([(19, NOTE)], definitions)

    def test_a_displayed_formulas_closing_superscript_becomes_a_mark_set_after_both_closing_delimiters(self) -> None:
        paragraphs, _definitions = self.written(DISPLAYED_FORMULA_READING)
        self.assertEqual([DISPLAYED_FORMULA_WITH_ITS_MARK], paragraphs)

    def test_a_superscript_opening_on_other_digits_stays_in_the_formula(self) -> None:
        paragraphs, _definitions = self.written(LONGER_EXPONENT_READING)
        self.assertEqual([r"4 $x^219$"], paragraphs)


if __name__ == "__main__":
    unittest.main()
