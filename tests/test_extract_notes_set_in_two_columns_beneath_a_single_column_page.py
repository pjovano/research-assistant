from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block
from _extract.layer import TextLayer
from _extract.layerlines import PageLines
from _extract.order import SingleColumnOrder

FILE_PAGE = 1
FONT = "helv"
BODY_SIZE = 11.0
NOTE_SIZE = 8.0
LEFT = 72.0
RIGHT_COLUMN_LEFT = 320.0
BODY = "In the end, these differences arise because the two worked within another paradigm."
FIRST_NOTE = "1 Leibniz, New Essays, Ch. V."
SECOND_NOTE = "2 In his paper on predication (in J."
CARRIED_ON = "McGuire and J. Bogen, eds.) Adams"
THIRD_NOTE = "3 Husserl speaks of formal ontology."
LINES = {BODY: (LEFT, 100.0, BODY_SIZE), FIRST_NOTE: (LEFT, 300.0, NOTE_SIZE),
         SECOND_NOTE: (LEFT, 340.0, NOTE_SIZE), CARRIED_ON: (RIGHT_COLUMN_LEFT, 310.0, NOTE_SIZE),
         THIRD_NOTE: (RIGHT_COLUMN_LEFT, 350.0, NOTE_SIZE)}
ENGINE_ORDER = [BODY, FIRST_NOTE, SECOND_NOTE, CARRIED_ON, THIRD_NOTE]


class TwoColumnNotesPdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "notes.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for text, (left, baseline, size) in LINES.items():
                page.insert_text((left, baseline), text, fontname=FONT, fontsize=size)
            document.save(self._path)
        return self._path


def engine_block(text: str, kind: str) -> Block:
    left, baseline, size = LINES[text]
    right = left + pymupdf.get_text_length(text, FONT, size)
    box = (left - 1.0, baseline - size, right + 1.0, baseline + size * 0.3)
    return Block(FILE_PAGE, kind, f"<p>{text}</p>", box, {}, f"/page/1/{list(LINES).index(text)}")


class TestNotesSetInTwoColumnsBeneathASingleColumnPage(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(TwoColumnNotesPdf(directory).write())
        self.addCleanup(self._layer.close)

    def _ordered(self) -> list[str]:
        blocks = [engine_block(text, TEXT_KIND if text == BODY else FOOTNOTE_KIND) for text in ENGINE_ORDER]
        ordered = SingleColumnOrder(PageLines(self._layer, FILE_PAGE, blocks)).ordered(blocks)
        return [block.plain_text for block in ordered]

    def test_the_notes_are_read_down_the_left_column_before_the_right_one(self) -> None:
        self.assertEqual(ENGINE_ORDER, self._ordered())


if __name__ == "__main__":
    unittest.main()
