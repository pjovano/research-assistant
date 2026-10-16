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
from _extract.markguard import MarkGuard

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
FIRST_BASELINE = 100.0
SECOND_BASELINE = 114.0
LEFT = 72.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)
QUOTED_LINE = "the True as Subject'' (18). It clearly deals with truth."
NEXT_LINE = "So the two concepts define it."
MARK = "13"
ENGINE_TWICE = ("<p>the True as Subject<sup>13</sup> (18). It clearly deals with truth.<sup>13</sup> "
                "So the two concepts define it.</p>")
ENGINE_ONCE_AT_ITS_WORD = ("<p>the True as Subject'' (18). It clearly deals with truth.<sup>13</sup> "
                           "So the two concepts define it.</p>")
ENGINE_ONCE_AFTER_A_MISREAD_WORD = ("<p>the True as Subject'' (18). It clearly deals with trnth.<sup>13</sup> "
                                    "So the two concepts define it.</p>")


class MarkedPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            page.insert_text((LEFT, FIRST_BASELINE), QUOTED_LINE, fontsize=FONT_SIZE, fontname=FONT)
            mark_left = LEFT + pymupdf.get_text_length(QUOTED_LINE, FONT, FONT_SIZE)
            page.insert_text((mark_left, FIRST_BASELINE - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
            page.insert_text((LEFT, SECOND_BASELINE), NEXT_LINE, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestMarksTheEngineReadsTwiceFromPixelsWhereTheTextLayerPrintsOne(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(MarkedPagePdf(Path(directory.name) / "page.pdf").write())
        self.addCleanup(layer.close)
        layer_html = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(FILE_PAGE, WHOLE_PAGE)))
        self.guard = MarkGuard(layer_html)

    def test_the_twin_raised_after_a_word_the_text_layer_marks_nowhere_is_dropped(self) -> None:
        self.assertEqual(ENGINE_TWICE.replace("Subject<sup>13</sup>", "Subject"), self.guard.corrected(ENGINE_TWICE))

    def test_a_mark_raised_as_often_as_the_text_layer_prints_it_stays(self) -> None:
        self.assertEqual(ENGINE_ONCE_AT_ITS_WORD, self.guard.corrected(ENGINE_ONCE_AT_ITS_WORD))

    def test_a_mark_raised_once_after_a_word_the_engine_misread_stays(self) -> None:
        self.assertEqual(ENGINE_ONCE_AFTER_A_MISREAD_WORD, self.guard.corrected(ENGINE_ONCE_AFTER_A_MISREAD_WORD))


if __name__ == "__main__":
    unittest.main()
