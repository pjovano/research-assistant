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
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
PRINTED_LINES = ["in half of the arbitrary urn-counter-pairings. Since even my", "late grandmother knew it."]
PRINTED_SENTENCE = "in half of the arbitrary urn-counter-pairings. Since even my late grandmother knew it."


class SentencePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, line in enumerate(PRINTED_LINES):
                page.insert_text((LEFT, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestHyphenatedCompoundsTheEngineReadsAsOneMisspeltWord(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(SentencePdf(Path(directory.name) / "sentence.pdf").write())
        self.addCleanup(layer.close)
        self.layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))

    def test_a_compound_the_engine_reads_without_a_letter_and_a_hyphen_takes_the_layers_spelling(self) -> None:
        engine_html = "<p>in half of the arbitrary uncounter-pairings. Since even my late grandmother knew it.</p>"
        self.assertEqual(f"<p>{PRINTED_SENTENCE}</p>", ProseGuard().corrected(engine_html, self.layer_html))

    def test_a_compound_the_engine_reads_a_letter_short_takes_the_layers_spelling(self) -> None:
        engine_html = "<p>in half of the arbitrary un-counter-pairings. Since even my late grandmother knew it.</p>"
        self.assertEqual(f"<p>{PRINTED_SENTENCE}</p>", ProseGuard().corrected(engine_html, self.layer_html))

    def test_a_compound_further_from_the_layers_than_a_slip_keeps_the_engines_reading(self) -> None:
        engine_html = "<p>in half of the arbitrary box-pairings. Since even my late grandmother knew it.</p>"
        self.assertEqual(engine_html, ProseGuard().corrected(engine_html, self.layer_html))


if __name__ == "__main__":
    unittest.main()
