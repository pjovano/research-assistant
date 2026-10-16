from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import FooterCase, NotedPage, body_block, notes_block
from _extract.blocks import FOOTNOTE_KIND, PageBlocks
from _extract.elements import Paragraph

NOTE = "Clearly, the premise is the negation."
UNPRINTED_SENTENCE = ""
FORMULA_READING = r"3 <math>\forall n(\neg B\lambda_n)^{19}</math>"
FORMULA_WITH_ITS_MARK = r"3 $\forall n(\neg B\lambda_n)$[^19]"
RAISED_EXPONENT_READING = r"4 <math>2^{10}</math>"


class FormulaMarkCase(FooterCase):
    def written(self, body_reading: str) -> tuple[list[str], list[tuple[int, str]]]:
        pages = [NotedPage(UNPRINTED_SENTENCE, "", (f"19 {NOTE}",))]
        engine_pages = [PageBlocks(1, [body_block(1, body_reading, ""), notes_block(1, FOOTNOTE_KIND, f"19 {NOTE}")])]
        structure = self.built(pages, engine_pages)
        paragraphs = [element.text for element in structure.elements() if isinstance(element, Paragraph)]
        return paragraphs, [(definition.label, definition.text) for definition in structure.definitions()]


class TestFootnoteMarksReadAsTheClosingSuperscriptOfAFormula(FormulaMarkCase):
    def test_the_formulas_closing_superscript_becomes_the_mark_of_the_note_printing_that_numeral(self) -> None:
        paragraphs, _definitions = self.written(FORMULA_READING)
        self.assertEqual([FORMULA_WITH_ITS_MARK], paragraphs)

    def test_the_note_takes_its_printed_numeral(self) -> None:
        _paragraphs, definitions = self.written(FORMULA_READING)
        self.assertEqual([(19, NOTE)], definitions)

    def test_a_superscript_no_note_prints_stays_in_the_formula(self) -> None:
        paragraphs, _definitions = self.written(RAISED_EXPONENT_READING)
        self.assertEqual([r"4 $2^{10}$"], paragraphs)


if __name__ == "__main__":
    unittest.main()
