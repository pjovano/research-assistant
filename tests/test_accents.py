from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from accents import composed


class TestSpacingAccentComposition(unittest.TestCase):
    def test_dieresis_before_its_letter(self) -> None:
        self.assertEqual("Gödel", composed("G¨odel"))

    def test_acute_before_its_letter(self) -> None:
        self.assertEqual("Poincaré, who", composed("Poincar´e, who"))

    def test_grave_before_its_letter(self) -> None:
        self.assertEqual("Solèr", composed("Sol`er"))

    def test_circumflex_before_its_letter(self) -> None:
        self.assertEqual("Noûs", composed("Noˆus"))

    def test_several_accents_in_one_line(self) -> None:
        self.assertEqual("Miklós Rédei", composed("Mikl´os R´edei"))

    def test_a_capital_takes_the_accent(self) -> None:
        self.assertEqual("Über", composed("¨Uber"))

    def test_a_dot_above_before_a_capital_composes_the_dotted_capital(self) -> None:
        self.assertEqual("İ.", composed("˙I."))

    def test_an_accent_over_a_dotless_i_composes_the_dotted_letter(self) -> None:
        self.assertEqual("í", composed("´ı"))

    def test_an_accent_a_dotless_letter_cannot_carry_leaves_the_pair_alone(self) -> None:
        self.assertEqual("¸ı", composed("¸ı"))

    def test_text_without_accents_is_unchanged(self) -> None:
        self.assertEqual("plain prose, nothing to do", composed("plain prose, nothing to do"))

    def test_already_composed_text_is_unchanged(self) -> None:
        self.assertEqual("Gödel", composed("Gödel"))

    def test_an_accent_with_no_precomposed_form_is_left_alone(self) -> None:
        self.assertEqual("¨q", composed("¨q"))

    def test_an_accent_before_a_digit_is_left_alone(self) -> None:
        self.assertEqual("2´3", composed("2´3"))

    def test_a_trailing_accent_is_left_alone(self) -> None:
        self.assertEqual("ends here ´", composed("ends here ´"))

    def test_an_accent_separated_from_a_letter_is_left_alone(self) -> None:
        self.assertEqual("¨\n\nof", composed("¨\n\nof"))

    def test_an_orphaned_accent_run_is_left_alone(self) -> None:
        self.assertEqual("¨\n¨\n¨\nlich", composed("¨\n¨\n¨\nlich"))


if __name__ == "__main__":
    unittest.main()
