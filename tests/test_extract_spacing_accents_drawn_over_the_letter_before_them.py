from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _layer_pdfs import RemappedTextPdf, StandIn

WHOLE_PAGE = Box(0.0, 0.0, 1000.0, 1000.0)
DOTLESS_I = StandIn("ı")
DIAERESIS_DRAWN_OVER_THE_LETTER_BEFORE = StandIn("¨", zero_width=True)
DIAERESIS_ADVANCING_TO_THE_LETTER_AFTER = StandIn("¨")
LINE_WITH_A_DIAERESIS_AFTER_ITS_LETTER = "an extremely na#^ve form"
EXPECTED_LINE = "an extremely naïve form"


class SpacingAccentCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def layer(self, lines: list[str], stand_ins: dict[str, StandIn]) -> TextLayer:
        layer = TextLayer(RemappedTextPdf(self._directory / "accents.pdf", lines, stand_ins).write())
        self.addCleanup(layer.close)
        return layer

    def written(self, lines: list[str], stand_ins: dict[str, StandIn]) -> str:
        layer = self.layer(lines, stand_ins)
        return BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))


class TestSpacingAccentDrawnOverTheLetterBeforeIt(SpacingAccentCase):
    def test_the_accent_composes_with_the_letter_it_is_drawn_over_in_the_written_text(self) -> None:
        stand_ins = {"#": DOTLESS_I, "^": DIAERESIS_DRAWN_OVER_THE_LETTER_BEFORE}
        self.assertEqual(EXPECTED_LINE, self.written([LINE_WITH_A_DIAERESIS_AFTER_ITS_LETTER], stand_ins))

    def test_the_accent_composes_with_the_letter_it_is_drawn_over_in_the_layer_lines(self) -> None:
        stand_ins = {"#": DOTLESS_I, "^": DIAERESIS_DRAWN_OVER_THE_LETTER_BEFORE}
        lines = self.layer([LINE_WITH_A_DIAERESIS_AFTER_ITS_LETTER], stand_ins).lines(1)
        self.assertEqual([EXPECTED_LINE], [line.text for line in lines])

    def test_an_accent_advancing_past_the_letter_before_it_still_composes_with_the_letter_after_it(self) -> None:
        lines = self.layer(["on G^odel"], {"^": DIAERESIS_ADVANCING_TO_THE_LETTER_AFTER}).lines(1)
        self.assertEqual(["on Gödel"], [line.text for line in lines])


if __name__ == "__main__":
    unittest.main()
