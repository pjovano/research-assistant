from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _extract.proseguard import ProseGuard

FILE_PAGE = 1
BUILTIN_FONT = "tiro"
EMBEDDED_FONT = "F0"
FONT_SIZE = 10.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)


class SentencePdf:
    def __init__(self, path: Path, sentence: str) -> None:
        self._path = path
        self._sentence = sentence

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_font(fontname=EMBEDDED_FONT, fontbuffer=pymupdf.Font(BUILTIN_FONT).buffer)
            page.insert_text((LEFT, BASELINE), self._sentence, fontsize=FONT_SIZE, fontname=EMBEDDED_FONT)
            document.save(self._path)
        return self._path


def guarded(engine_html: str, printed_sentence: str) -> str:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(SentencePdf(Path(directory) / "sentence.pdf", printed_sentence).write())
        try:
            layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        finally:
            layer.close()
    return ProseGuard().corrected(engine_html, layer_html)


class TestQuotationMarksTheEngineReadsStraightBesideANotationSpan(unittest.TestCase):
    def test_quotes_enclosing_a_notation_span_take_the_layers_curly_forms(self) -> None:
        engine_html = "<p>every natural kind noun '<math>N_k</math>' refers to a kind.</p>"
        printed = "every natural kind noun ‘Nk’ refers to a kind."
        expected = "<p>every natural kind noun ‘<math>N_k</math>’ refers to a kind.</p>"
        self.assertEqual(expected, guarded(engine_html, printed))

    def test_an_opening_quote_before_a_notation_span_takes_the_curly_form_its_partner_takes(self) -> None:
        engine_html = "<p>By these standards '<math>F</math>(phlogiston)' is not meaningful.</p>"
        printed = "By these standards ‘F(phlogiston)’ is not meaningful."
        expected = "<p>By these standards ‘<math>F</math>(phlogiston)’ is not meaningful.</p>"
        self.assertEqual(expected, guarded(engine_html, printed))

    def test_an_opening_quote_after_a_notation_span_takes_the_curly_form_its_partner_takes(self) -> None:
        engine_html = "<p>a natural kind noun <math>K</math> 'water' refers to <math>K</math>.</p>"
        printed = "a natural kind noun K ‘water’ refers to K."
        expected = "<p>a natural kind noun <math>K</math> ‘water’ refers to <math>K</math>.</p>"
        self.assertEqual(expected, guarded(engine_html, printed))

    def test_a_quote_beside_a_notation_span_the_layer_prints_another_count_of_stays(self) -> None:
        engine_html = "<p>the noun '<math>N_k</math> refers to a kind.</p>"
        printed = "the noun ‘‘Nk’’ refers to a kind."
        self.assertEqual(engine_html, guarded(engine_html, printed))


if __name__ == "__main__":
    unittest.main()
