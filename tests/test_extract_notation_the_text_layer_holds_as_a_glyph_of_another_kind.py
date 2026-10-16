from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.guardedmath import GuardedMath, NotationLog
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of

FILE_PAGE = 1
PROSE_FONT = "tiro"
FONT_SIZE = 10.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
OPENING = "so "
CLOSING = " holds"


class SentencePdf:
    def __init__(self, path: Path, formula_text: str) -> None:
        self._path = path
        self._formula_text = formula_text

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            sentence = OPENING + self._formula_text + CLOSING
            page.insert_text((LEFT, BASELINE), sentence, fontsize=FONT_SIZE, fontname=PROSE_FONT)
            document.save(self._path)
        return self._path


class GuardedSentence:
    def __init__(self, test: unittest.TestCase, formula_text: str, engine_latex: str) -> None:
        directory = tempfile.TemporaryDirectory()
        test.addCleanup(directory.cleanup)
        layer = TextLayer(SentencePdf(Path(directory.name) / "sentence.pdf", formula_text).write())
        test.addCleanup(layer.close)
        layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        self.engine_html = f"<p>so <math>{engine_latex}</math> holds</p>"
        self.log = NotationLog()
        self.checked = GuardedMath(self.log).checked(FILE_PAGE, self.engine_html, layer_html)


class TestNotationTheTextLayerHoldsAsAGlyphOfAnotherKind(unittest.TestCase):
    def test_a_letter_the_text_layer_holds_as_a_digit_is_kept_as_the_engine_read_it(self) -> None:
        sentence = GuardedSentence(self, "H20", "\\text{H}_2\\text{O}")
        self.assertEqual(sentence.engine_html, sentence.checked)

    def test_a_digit_the_text_layer_holds_as_a_letter_is_kept_as_the_engine_read_it(self) -> None:
        sentence = GuardedSentence(self, "Si", "S_1")
        self.assertEqual(sentence.engine_html, sentence.checked)

    def test_a_digit_the_text_layer_holds_as_a_punctuation_mark_is_kept_as_the_engine_read_it(self) -> None:
        sentence = GuardedSentence(self, "L\\", "L_1")
        self.assertEqual(sentence.engine_html, sentence.checked)

    def test_the_formula_whose_glyph_the_text_layer_holds_as_another_kind_is_flagged(self) -> None:
        sentence = GuardedSentence(self, "H20", "\\text{H}_2\\text{O}")
        self.assertEqual(["file p. 1: flagged \\text{H}_2\\text{O} (text layer: H20)"], sentence.log.entries())

    def test_a_letter_the_text_layer_holds_as_another_letter_is_still_corrected(self) -> None:
        sentence = GuardedSentence(self, "Lx", "E_x")
        self.assertEqual("<p>so <math>L_x</math> holds</p>", sentence.checked)


if __name__ == "__main__":
    unittest.main()
