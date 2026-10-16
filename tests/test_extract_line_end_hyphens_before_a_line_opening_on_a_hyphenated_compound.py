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

FONT = "tiro"
FONT_SIZE = 10.0
LEFT = 72.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
WHOLE_PAGE = Box(0.0, 0.0, 612.0, 792.0)


class TwoLinePdf:
    def __init__(self, path: Path, lines: list[str]) -> None:
        self._path = path
        self._lines = lines

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row, line in enumerate(self._lines):
                page.insert_text((LEFT, FIRST_BASELINE + row * LINE_PITCH), line, fontname=FONT, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def written(lines: list[str]) -> str:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(TwoLinePdf(Path(directory) / "hyphens.pdf", lines).write())
        text = BlockHtml(Hyphens(layer)).of(rows_of(layer.chars_in(1, WHOLE_PAGE)))
        layer.close()
    return text


class TestLineEndHyphensBeforeALineOpeningOnAHyphenatedCompound(unittest.TestCase):
    def test_the_hyphen_between_two_words_the_work_prints_apart_and_never_joined_is_kept(self) -> None:
        self.assertEqual("of fire-water-air-earth into conformity. Fire is hot and water is wet.",
                         written(["of fire-", "water-air-earth into conformity.", "Fire is hot and water is wet."]))

    def test_the_hyphen_inside_a_word_the_work_prints_joined_still_joins_it(self) -> None:
        self.assertEqual("are context-dependent. The text, pro and con, in context.",
                         written(["are con-", "text-dependent.", "The text, pro and con, in context."]))

    def test_the_hyphen_after_a_syllable_the_work_never_prints_alone_still_joins_the_word(self) -> None:
        self.assertEqual("the taking-as of it", written(["the tak-", "ing-as of it"]))

    def test_the_hyphen_before_a_plain_word_still_joins_the_word(self) -> None:
        self.assertEqual("that massive accretion into conformity",
                         written(["that massive accre-", "tion into conformity"]))


if __name__ == "__main__":
    unittest.main()
