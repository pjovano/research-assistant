from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from test_extract_marks_the_engine_reads_twice_from_pixels_where_the_text_layer_prints_one import (
    FILE_PAGE, MARK, WHOLE_PAGE, MarkedPagePdf,
)
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _extract.markguard import MarkGuard

MISREAD_NUMERAL = "3"
ENGINE_WITH_A_MISREAD_NUMERAL = ("<p>the True as Subject'' (18). It clearly deals with truth.<sup>{number}</sup> "
                                 "So the two concepts define it.</p>")


class TestMarksTheEngineReadsFromPixelsUnderAnotherNumeralThanTheTextLayerRaises(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(MarkedPagePdf(Path(directory.name) / "page.pdf").write())
        self.addCleanup(layer.close)
        layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        self.guard = MarkGuard(layer_html)

    def test_the_mark_takes_the_numeral_the_text_layer_raises_after_its_word(self) -> None:
        self.assertEqual(ENGINE_WITH_A_MISREAD_NUMERAL.format(number=MARK),
                         self.guard.corrected(ENGINE_WITH_A_MISREAD_NUMERAL.format(number=MISREAD_NUMERAL)))


if __name__ == "__main__":
    unittest.main()
