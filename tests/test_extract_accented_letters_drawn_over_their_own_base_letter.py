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
ACUTE_E_DRAWN_OVER_THE_LETTER_AFTER = StandIn("é", zero_width=True)
GRAVE_E_DRAWN_OVER_THE_LETTER_AFTER = StandIn("è", zero_width=True)
ACUTE_E_ADVANCING = StandIn("é")
OVERSTRUCK_STAND_INS = {"#": ACUTE_E_DRAWN_OVER_THE_LETTER_AFTER, "^": GRAVE_E_DRAWN_OVER_THE_LETTER_AFTER}
LINE_OF_OVERSTRUCK_LETTERS = "Poincar#e, Science et M#ethode, Biblioth^eque"
EXPECTED_LINE = "Poincaré, Science et Méthode, Bibliothèque"


class OverstruckAccentCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def layer(self, lines: list[str], stand_ins: dict[str, StandIn]) -> TextLayer:
        layer = TextLayer(RemappedTextPdf(self._directory / "overstruck.pdf", lines, stand_ins).write())
        self.addCleanup(layer.close)
        return layer

    def line_texts(self, lines: list[str], stand_ins: dict[str, StandIn]) -> list[str]:
        return [line.text for line in self.layer(lines, stand_ins).lines(1)]


class TestAccentedLetterDrawnOverItsOwnBaseLetter(OverstruckAccentCase):
    def test_the_base_letter_under_the_accented_letter_is_dropped_from_the_layer_lines(self) -> None:
        self.assertEqual([EXPECTED_LINE], self.line_texts([LINE_OF_OVERSTRUCK_LETTERS], OVERSTRUCK_STAND_INS))

    def test_the_base_letter_under_the_accented_letter_is_dropped_from_the_written_text(self) -> None:
        layer = self.layer([LINE_OF_OVERSTRUCK_LETTERS], OVERSTRUCK_STAND_INS)
        written = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
        self.assertEqual(EXPECTED_LINE, written)

    def test_an_accented_letter_set_beside_its_base_letter_keeps_both(self) -> None:
        self.assertEqual(["créée"], self.line_texts(["cr**e"], {"*": ACUTE_E_ADVANCING}))


if __name__ == "__main__":
    unittest.main()
