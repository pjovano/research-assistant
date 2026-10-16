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


class TestQuotationMarksTheEngineReadsStraightWhereTheLayerSetsThemCurly(unittest.TestCase):
    def guarded(self, engine_html: str, printed_sentence: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(SentencePdf(Path(directory) / "sentence.pdf", printed_sentence).write())
            try:
                layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
            finally:
                layer.close()
        return ProseGuard().corrected(engine_html, layer_html)

    def test_straight_apostrophes_and_single_quotes_take_the_layers_curly_forms(self) -> None:
        engine_html = "<p>Penrose's calculus of 'progressive diagrams' holds.</p>"
        printed = "Penrose’s calculus of ‘progressive diagrams’ holds."
        self.assertEqual(f"<p>{printed}</p>", self.guarded(engine_html, printed))

    def test_straight_double_quotes_take_the_layers_curly_forms(self) -> None:
        engine_html = '<p>The so-called "wiggle room" remains.</p>'
        printed = "The so-called “wiggle room” remains."
        self.assertEqual(f"<p>{printed}</p>", self.guarded(engine_html, printed))

    def test_a_misread_word_beside_quotes_the_layer_sets_in_another_form_takes_the_layers_spelling(self) -> None:
        engine_html = "<p>between “reasonable” [Verstandigen] and “speculative” [Spekulativen] here</p>"
        printed = "between ‘‘reasonable’’ [Verstandigem] and ‘‘speculative’’ [Spekulativem] here"
        expected = "<p>between “reasonable” [Verstandigem] and “speculative” [Spekulativem] here</p>"
        self.assertEqual(expected, self.guarded(engine_html, printed))

    def test_a_straight_mark_the_layer_also_sets_straight_stays(self) -> None:
        engine_html = "<p>Penrose's calculus holds.</p>"
        self.assertEqual(engine_html, self.guarded(engine_html, "Penrose's calculus holds."))


if __name__ == "__main__":
    unittest.main()
