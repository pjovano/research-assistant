from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.guardedmath import GuardedMath, NotationLog
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _layer_pdfs import (
    FIRST_BASELINE, FONT_NAME, FONT_SIZE, GLYPH_WIDTH, LEFT_MARGIN, RemappedTextPdf, StandIn,
)

FILE_PAGE = 1
WHOLE_PAGE = Box(0.0, 0.0, 1000.0, 1000.0)
GLYPH_UNITS_PER_EM = 1000
RUN_GAP_POINTS = 8.0
STAND_INS = {"^": StandIn("̸", zero_width=True), "#": StandIn("≡"), "%": StandIn("α"),
             "&": StandIn("η"), "~": StandIn("̓", zero_width=True), "{": StandIn("́", zero_width=True),
             "<": StandIn("̔", zero_width=True), ">": StandIn("̀", zero_width=True),
             "_": StandIn("̄", zero_width=True)}
RUNS_WITH_THE_OVERLAY_DRAWN_OVER_THE_RELATION = ["so p", "^#q holds"]
LINE_WITH_THE_OVERLAY_DRAWN_OVER_THE_SIGN_BEFORE = "so =^ #q holds"
LINE_WITH_TWO_MARKS_ON_A_GREEK_LETTER = "so %~{e holds"
LINE_WITH_TWO_MARKS_ENDING_A_GREEK_WORD = "so &<> %llo holds"
LINE_WITH_A_MARK_ON_A_LETTER_WITHOUT_A_PRECOMPOSED_FORM = "so n_a holds"
LINE_WITH_A_MARK_ENDING_A_WORD_ON_A_LETTER_WITHOUT_A_PRECOMPOSED_FORM = "so n_ a holds"
ENGINE_HTML = "<p>so <math>p \\neq q</math> holds</p>"


class SpacedRunsPdf(RemappedTextPdf):
    def draw(self, page, lines: list[str]) -> None:
        left = LEFT_MARGIN
        for run in lines:
            page.insert_text((left, FIRST_BASELINE), run, fontname=FONT_NAME, fontsize=FONT_SIZE)
            left += len(run) * GLYPH_WIDTH / GLYPH_UNITS_PER_EM * FONT_SIZE + RUN_GAP_POINTS


class CombiningMarkCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._path = directory / "marks.pdf"

    def layer(self, pdf: RemappedTextPdf) -> TextLayer:
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        return layer

    def line_text(self, line: str) -> str:
        return self.layer(RemappedTextPdf(self._path, [line], STAND_INS)).lines(FILE_PAGE)[0].text

    def overlay_layer(self) -> TextLayer:
        return self.layer(SpacedRunsPdf(self._path, RUNS_WITH_THE_OVERLAY_DRAWN_OVER_THE_RELATION, STAND_INS))


class TestNegationOverlayDrawnOverTheRelationAfterABlank(CombiningMarkCase):
    def test_the_overlay_composes_with_the_relation_it_is_drawn_over(self) -> None:
        self.assertEqual("so p ≢q holds", self.overlay_layer().lines(FILE_PAGE)[0].text)

    def test_the_notation_guard_corrects_the_formula_to_the_negated_relation(self) -> None:
        layer = self.overlay_layer()
        layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        checked = GuardedMath(NotationLog()).checked(FILE_PAGE, ENGINE_HTML, layer_html)
        self.assertEqual("<p>so <math>p \\not\\equiv q</math> holds</p>", checked)


class TestCombiningMarksDrawnOverTheCharBeforeThem(CombiningMarkCase):
    def test_an_overlay_drawn_over_the_sign_before_it_stays_on_it(self) -> None:
        self.assertEqual("so ≠ ≡q holds", self.line_text(LINE_WITH_THE_OVERLAY_DRAWN_OVER_THE_SIGN_BEFORE))

    def test_the_second_of_two_marks_on_a_greek_letter_stays_on_it(self) -> None:
        self.assertEqual("so ἄe holds", self.line_text(LINE_WITH_TWO_MARKS_ON_A_GREEK_LETTER))

    def test_two_marks_ending_a_greek_word_stay_on_its_letter_before_a_blank_and_a_vowel(self) -> None:
        self.assertEqual("so ἣ αllo holds", self.line_text(LINE_WITH_TWO_MARKS_ENDING_A_GREEK_WORD))

    def test_a_mark_on_a_letter_without_a_precomposed_form_stays_on_it(self) -> None:
        self.assertEqual("so n̄a holds", self.line_text(LINE_WITH_A_MARK_ON_A_LETTER_WITHOUT_A_PRECOMPOSED_FORM))

    def test_a_mark_ending_a_word_on_a_letter_without_a_precomposed_form_stays_on_it(self) -> None:
        line = LINE_WITH_A_MARK_ENDING_A_WORD_ON_A_LETTER_WITHOUT_A_PRECOMPOSED_FORM
        self.assertEqual("so n̄ a holds", self.line_text(line))


if __name__ == "__main__":
    unittest.main()
