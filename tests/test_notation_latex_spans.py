from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from notation import DISPLAY_MATH, INLINE_MATH, display_latex_span, inline_latex_span, latex_span

EXPRESSION = r"\alpha + \beta"


class TestLatexSpans(unittest.TestCase):
    def test_an_inline_span_is_the_trimmed_expression_between_single_delimiters(self) -> None:
        self.assertEqual(f"{INLINE_MATH}{EXPRESSION}{INLINE_MATH}", inline_latex_span(f" {EXPRESSION} "))

    def test_a_display_span_is_the_expression_between_double_delimiters(self) -> None:
        self.assertEqual(f"{DISPLAY_MATH}{EXPRESSION}{DISPLAY_MATH}", display_latex_span(EXPRESSION))

    def test_an_expression_of_control_characters_alone_is_no_span(self) -> None:
        self.assertEqual(("", ""), (inline_latex_span("\x00​"), display_latex_span(" \x07 ")))

    def test_the_flagged_name_kept_for_its_callers_picks_the_matching_span(self) -> None:
        self.assertEqual((display_latex_span(EXPRESSION), inline_latex_span(EXPRESSION)),
                         (latex_span(EXPRESSION, True), latex_span(EXPRESSION, False)))


if __name__ == "__main__":
    unittest.main()
