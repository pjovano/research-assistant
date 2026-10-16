from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.guardedmath import GuardedMath, NotationLog

PAGE = 148
ENGINE_HTML = "<p>expand <math>\\mathcal{E}</math> by <math>\\square</math> here</p>"
LAYER_HTML = "expand L by □ here"


class TestGuardedMath(unittest.TestCase):
    def setUp(self) -> None:
        self.log = NotationLog()
        self.checked = GuardedMath(self.log).checked(PAGE, ENGINE_HTML, LAYER_HTML)

    def test_a_misread_formula_is_replaced_inside_its_math_element(self) -> None:
        self.assertEqual("<p>expand <math>\\mathcal{L}</math> by <math>\\square</math> here</p>", self.checked)

    def test_only_formulas_the_guard_did_not_agree_are_logged(self) -> None:
        self.assertEqual(["file p. 148: corrected \\mathcal{E} to \\mathcal{L} (text layer: L)"],
                         self.log.entries())

    def test_the_same_formula_checked_twice_is_logged_once(self) -> None:
        GuardedMath(self.log).checked(PAGE, ENGINE_HTML, LAYER_HTML)
        self.assertEqual(1, len(self.log.entries()))

    def test_escaped_latex_is_checked_unescaped_and_written_back_escaped(self) -> None:
        engine_html = "<p>so <math>a &lt; b</math> holds</p>"
        self.assertEqual(engine_html, GuardedMath(NotationLog()).checked(PAGE, engine_html, "so a < b holds"))

    def test_a_flagged_formula_keeps_the_engine_reading_and_is_logged(self) -> None:
        log = NotationLog()
        GuardedMath(log).checked(PAGE, "<p>so <math>\\Gamma</math> holds</p>", "so ΓΔΘΛ holds")
        self.assertEqual(["file p. 148: flagged \\Gamma (text layer: ΓΔΘΛ)"], log.entries())


if __name__ == "__main__":
    unittest.main()
