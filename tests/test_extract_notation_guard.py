from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.formulasymbols import FormulaSymbols, folded, folded_units
from _extract.notationguard import (
    AGREED, CORRECTED, FLAGGED, FormulaRegions, NotationGuard,
)

RULE_LATEX = ("\\frac{\\Gamma \\succ A, \\Delta \\quad \\Theta \\succ B, \\Delta}"
              "{\\Gamma, \\Theta \\succ A \\otimes B, \\Delta, \\Delta} [\\otimes \\text{R}]")
RULE_LAYER = "Γ ≻ A, Δ Θ ≻ B, Λ [⊗R] Γ, Θ ≻ A ⊗ B, Δ, Λ"
SENTENCE_HTML = ("<p>We can therefore expand our language <math>\\mathcal{E}</math> to"
                 " <math>\\mathcal{E}^\\square</math> by including sentences in which <math>\\square</math>"
                 " occurs as a one-place connective.</p>")
SENTENCE_LAYER = ("We can therefore expand our language L to L<sup>□</sup> by including sentences in which □ occurs"
                  " as a one-place connective.")


class TestFormulaSymbols(unittest.TestCase):
    def test_the_symbols_of_a_fraction_are_its_numerator_then_its_denominator(self) -> None:
        self.assertEqual("Γ≻A,ΔΘ", FormulaSymbols("\\frac{\\Gamma \\succ A, \\Delta}{\\Theta}").text())

    def test_an_environment_name_is_not_a_symbol(self) -> None:
        self.assertEqual("ab", FormulaSymbols("\\begin{cases} a & b \\end{cases}").text())

    def test_a_sized_delimiter_is_not_a_symbol(self) -> None:
        self.assertEqual("x", FormulaSymbols("\\left( x \\right) \\bigl\\langle").text())

    def test_a_letter_in_a_font_command_is_the_letter(self) -> None:
        self.assertEqual("EN", FormulaSymbols("\\mathcal{E}\\mathbb{N}").text())

    def test_a_negated_relation_is_one_symbol(self) -> None:
        self.assertEqual("x≠y", FormulaSymbols("x \\neq y").text())


class TestFolding(unittest.TestCase):
    def test_an_overlay_composes_with_the_character_it_crosses(self) -> None:
        self.assertEqual("x≠y", folded("x ≠ y"))

    def test_a_script_letter_folds_to_its_plain_letter(self) -> None:
        self.assertEqual("LA", folded("ℒ 𝔄"))

    def test_a_minus_sign_and_an_ellipsis_fold_to_their_ascii_forms(self) -> None:
        self.assertEqual("a-b...", folded("a − b …"))


class TestFoldedUnits(unittest.TestCase):
    def test_a_bar_and_a_tilde_are_one_snake_turnstile(self) -> None:
        self.assertEqual(["□", "A", "|∼", "◊", "A"], folded_units("□A ∣∼ ◊A"))

    def test_a_bar_and_an_equals_sign_are_one_double_turnstile(self) -> None:
        self.assertEqual(["I", "⊨", "φ"], folded_units("I |= ϕ"))

    def test_the_braces_a_layout_draws_are_not_symbols(self) -> None:
        self.assertEqual(["a", "b"], folded_units("{a b}"))

    def test_the_units_of_a_formula_join_a_bar_and_a_tilde(self) -> None:
        self.assertEqual(["|∼", "A"], [unit.text for unit in FormulaSymbols("\\mid\\!\\sim A").units()])


class TestNotationGuard(unittest.TestCase):
    def test_a_formula_whose_symbols_match_in_another_order_is_agreed(self) -> None:
        verdict = NotationGuard().checked("\\frac{a}{b} [R]", "a [R] b")
        self.assertEqual((AGREED, "\\frac{a}{b} [R]"), (verdict.status, verdict.latex))

    def test_a_misread_greek_letter_is_corrected_at_the_positions_the_text_layer_names(self) -> None:
        expected = ("\\frac{\\Gamma \\succ A, \\Delta \\quad \\Theta \\succ B, \\Lambda}"
                    "{\\Gamma, \\Theta \\succ A \\otimes B, \\Delta, \\Lambda} [\\otimes \\text{R}]")
        verdict = NotationGuard().checked(RULE_LATEX, RULE_LAYER)
        self.assertEqual((CORRECTED, expected), (verdict.status, verdict.latex))

    def test_a_misread_letter_keeps_its_font_command(self) -> None:
        verdict = NotationGuard().checked("\\mathcal{E}^\\square", "L□")
        self.assertEqual((CORRECTED, "\\mathcal{L}^\\square"), (verdict.status, verdict.latex))

    def test_a_dropped_symbol_is_flagged_and_the_formula_kept(self) -> None:
        verdict = NotationGuard().checked("\\Gamma \\succ A", "Γ ≻ A, Δ")
        self.assertEqual((FLAGGED, "\\Gamma \\succ A"), (verdict.status, verdict.latex))

    def test_a_relation_misread_as_another_is_corrected_to_the_layers_composite(self) -> None:
        verdict = NotationGuard().checked("\\square A \\succ \\diamond A", "□A ∣∼ ◊A")
        self.assertEqual((CORRECTED, "\\square A \\mid\\!\\sim \\diamond A"), (verdict.status, verdict.latex))

    def test_one_misread_repeated_through_a_formula_is_corrected_everywhere(self) -> None:
        latex = "\\mathcal{J} \\frac{\\mathcal{J}(t_0) \\dots \\mathcal{J}(t_r)}{x_0}(t) = \\mathcal{J}"
        verdict = NotationGuard().checked(latex, "II(t0)...I(tr)x0 (t) = I")
        self.assertEqual((CORRECTED, latex.replace("J", "I")), (verdict.status, verdict.latex))

    def test_a_letter_in_the_wrong_alphabet_takes_the_alphabet_the_text_layer_names(self) -> None:
        verdict = NotationGuard().checked("\\mathcal{J}(R) = \\mathfrak{A}", "ℑ(R) = 𝔄")
        self.assertEqual((CORRECTED, "\\mathfrak{I}(R) = \\mathfrak{A}"), (verdict.status, verdict.latex))

    def test_a_bare_letter_the_text_layer_sets_in_fraktur_gains_the_fraktur_command(self) -> None:
        verdict = NotationGuard().checked("I \\models \\varphi", "ℑ |= ϕ")
        self.assertEqual((CORRECTED, "\\mathfrak{I} \\models \\varphi"), (verdict.status, verdict.latex))

    def test_a_letter_whose_alphabet_the_text_layer_does_not_name_keeps_its_command(self) -> None:
        verdict = NotationGuard().checked("\\mathbb{N}", "N")
        self.assertEqual((AGREED, "\\mathbb{N}"), (verdict.status, verdict.latex))

    def test_a_letter_the_text_layer_sets_in_two_alphabets_is_left_as_read(self) -> None:
        verdict = NotationGuard().checked("\\mathcal{A} \\cup \\mathcal{A}", "𝔄 ∪ 𝔸")
        self.assertEqual(FLAGGED, verdict.status)

    def test_a_font_group_of_several_letters_in_the_wrong_alphabet_is_flagged(self) -> None:
        verdict = NotationGuard().checked("\\mathcal{AB}", "𝔄𝔅")
        self.assertEqual((FLAGGED, "\\mathcal{AB}"), (verdict.status, verdict.latex))

    def test_a_formula_needing_many_different_substitutions_is_flagged(self) -> None:
        verdict = NotationGuard().checked("\\alpha \\beta \\gamma \\delta", "w x y z")
        self.assertEqual(FLAGGED, verdict.status)

    def test_a_formula_with_no_text_layer_characters_is_flagged(self) -> None:
        self.assertEqual(FLAGGED, NotationGuard().checked("\\Gamma", "").status)


class TestFormulaRegions(unittest.TestCase):
    def test_each_formula_takes_the_text_layer_characters_between_its_prose_anchors(self) -> None:
        self.assertEqual(["L", "L□", "□"], FormulaRegions(SENTENCE_HTML, SENTENCE_LAYER).regions())

    def test_a_displayed_formula_alone_in_its_block_takes_the_whole_block(self) -> None:
        html_text = '<p block-type="Equation"><math display="block">\\frac{a}{b}</math></p>'
        self.assertEqual(["a b"], FormulaRegions(html_text, "a b").regions())

    def test_formulas_with_no_prose_between_them_have_no_region(self) -> None:
        html_text = "<p>so <math>a</math><math>b</math> holds</p>"
        self.assertEqual(["", ""], FormulaRegions(html_text, "so ab holds").regions())
