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
FONT = "tiro"
FONT_SIZE = 10.0
BASELINE = 100.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
PRINTED_SENTENCE = "The claim recurs in the collected works (Werke I/4: 330; 432) and in the letters."


class SentencePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_text((LEFT, BASELINE), PRINTED_SENTENCE, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestWordsJoinedByASlashToANumeralTheEngineReadsAsLetters(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(SentencePdf(Path(directory.name) / "sentence.pdf").write())
        self.addCleanup(layer.close)
        self.layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))

    def test_a_slash_and_numeral_the_engine_reads_as_a_letter_take_the_layers_whole_token(self) -> None:
        engine_html = "<p>The claim recurs in the collected works (Werke II: 330; 432) and in the letters.</p>"
        self.assertEqual(f"<p>{PRINTED_SENTENCE}</p>", ProseGuard().corrected(engine_html, self.layer_html))

    def test_a_slash_joined_token_the_engine_reads_whole_keeps_the_engines_reading(self) -> None:
        engine_html = f"<p>{PRINTED_SENTENCE}</p>"
        self.assertEqual(engine_html, ProseGuard().corrected(engine_html, self.layer_html))

    def test_a_word_far_from_the_layers_letters_keeps_the_engines_reading(self) -> None:
        engine_html = "<p>The claim recurs in the collected works (Werke XVII: 330; 432) and in the letters.</p>"
        self.assertEqual(engine_html, ProseGuard().corrected(engine_html, self.layer_html))


if __name__ == "__main__":
    unittest.main()
