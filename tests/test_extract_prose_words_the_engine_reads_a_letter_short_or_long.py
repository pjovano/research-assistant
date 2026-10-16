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
PRINTED_SENTENCE = "the structureal-formal gap and a formal gap remain"
CORRECTED_HTML = f"<p>{PRINTED_SENTENCE}</p>"


class SentencePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_text((LEFT, BASELINE), PRINTED_SENTENCE, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestProseWordsTheEngineReadsALetterShortOrLong(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(SentencePdf(Path(directory.name) / "sentence.pdf").write())
        self.addCleanup(layer.close)
        self.layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))

    def test_a_word_the_engine_reads_a_letter_short_takes_the_text_layers_spelling(self) -> None:
        engine_html = "<p>the structural-formal gap and a formal gap remain</p>"
        self.assertEqual(CORRECTED_HTML, ProseGuard().corrected(engine_html, self.layer_html))

    def test_a_word_the_engine_reads_a_letter_long_takes_the_text_layers_spelling(self) -> None:
        engine_html = "<p>the structureal-formal gap and a formal gasp remain</p>"
        self.assertEqual(CORRECTED_HTML, ProseGuard().corrected(engine_html, self.layer_html))

    def test_a_word_further_from_the_layers_than_a_slip_keeps_the_engines_reading(self) -> None:
        engine_html = "<p>the structural-formal gap and a formal breach remain</p>"
        expected = "<p>the structureal-formal gap and a formal breach remain</p>"
        self.assertEqual(expected, ProseGuard().corrected(engine_html, self.layer_html))


if __name__ == "__main__":
    unittest.main()
