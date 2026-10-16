from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from latex_symbols import MathJaxLatex

UNRENDERED = {"\\llbracket": "⟦", "\\rrbracket": "⟧", "\\parr": "⅋", "\\llparenthesis": "⦇",
              "\\rrparenthesis": "⦈", "\\VDash": "⊫", "\\Dashv": "⫤", "\\dashV": "⫣", "\\DashV": "⫥"}


class TestAMacroMathJaxCannotRenderIsWrittenAsItsCharacter(unittest.TestCase):
    def test_each_unrendered_macro_becomes_its_character(self) -> None:
        for macro, character in UNRENDERED.items():
            with self.subTest(macro=macro):
                self.assertEqual(f"x {character} y", MathJaxLatex().safe(f"x {macro} y"))

    def test_a_macro_mathjax_renders_is_kept(self) -> None:
        self.assertEqual("x \\models y", MathJaxLatex().safe("x \\models y"))


if __name__ == "__main__":
    unittest.main()
