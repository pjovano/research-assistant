from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block
from _extract.layer import TextLayer
from _extract.layerlines import PageLines
from _extract.order import SingleColumnOrder

FILE_PAGE = 1
FONT = "helv"
BODY_SIZE = 11.0
MARGIN_SIZE = 8.0
NOTE_SIZE = 8.0
LEFT = 72.0
MARGIN_LEFT = 30.0
SECOND_NOTE_LEFT = 200.0
HEADING_LEFT = 200.0
TITLE_LEFT = 150.0
RIGHT_COLUMN_LEFT = 300.0
TITLE = "II. Cosmological ideas"
MARGIN_REFERENCE = "[4:338]"
FIRST_PROSE = "This product of pure reason in its transcendent use is its most remarkable phenomenon."
SECTION_NUMBER = "§51"
SECOND_PROSE = "In the first place, the usefulness of a system of categories is here revealed clearly."
FIRST_NOTE = "g Gegenstand"
SECOND_NOTE = "h Objekt"
LEFT_COLUMN = "The left column sets one argument."
RIGHT_COLUMN = "The right column sets another one."
LINES = {TITLE: (TITLE_LEFT, 80.0, BODY_SIZE), MARGIN_REFERENCE: (MARGIN_LEFT, 84.0, MARGIN_SIZE),
         FIRST_PROSE: (LEFT, 110.0, BODY_SIZE), SECTION_NUMBER: (HEADING_LEFT, 150.0, BODY_SIZE),
         SECOND_PROSE: (LEFT, 180.0, BODY_SIZE), FIRST_NOTE: (LEFT, 300.0, NOTE_SIZE),
         SECOND_NOTE: (SECOND_NOTE_LEFT, 300.0, NOTE_SIZE), LEFT_COLUMN: (LEFT, 400.0, NOTE_SIZE),
         RIGHT_COLUMN: (RIGHT_COLUMN_LEFT, 400.0, NOTE_SIZE)}
KINDS = {TITLE: HEADING_KIND, MARGIN_REFERENCE: TEXT_KIND, FIRST_PROSE: TEXT_KIND, SECTION_NUMBER: HEADING_KIND,
         SECOND_PROSE: TEXT_KIND, FIRST_NOTE: FOOTNOTE_KIND, SECOND_NOTE: FOOTNOTE_KIND, LEFT_COLUMN: TEXT_KIND,
         RIGHT_COLUMN: TEXT_KIND}
ENGINE_ORDER = [SECTION_NUMBER, MARGIN_REFERENCE, TITLE, FIRST_PROSE, SECOND_PROSE, FIRST_NOTE, SECOND_NOTE]
TWO_COLUMN_ENGINE_ORDER = [SECTION_NUMBER, MARGIN_REFERENCE, TITLE, RIGHT_COLUMN, LEFT_COLUMN]
PAGE_ORDER = [TITLE, MARGIN_REFERENCE, FIRST_PROSE, SECTION_NUMBER, SECOND_PROSE, FIRST_NOTE, SECOND_NOTE]


class MarginedPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "margined.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for text, (left, baseline, size) in LINES.items():
                page.insert_text((left, baseline), text, fontname=FONT, fontsize=size)
            document.save(self._path)
        return self._path


def engine_block(text: str) -> Block:
    left, baseline, size = LINES[text]
    right = left + pymupdf.get_text_length(text, FONT, size)
    box = (left - 1.0, baseline - size, right + 1.0, baseline + size * 0.3)
    return Block(FILE_PAGE, KINDS[text], f"<p>{text}</p>", box, {}, f"/page/1/{list(LINES).index(text)}")


class TestSingleColumnPagesWithBlocksBesideTheColumn(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(MarginedPagePdf(directory).write())
        self.addCleanup(self._layer.close)

    def _ordered(self, texts: list[str]) -> list[str]:
        blocks = [engine_block(text) for text in texts]
        ordered = SingleColumnOrder(PageLines(self._layer, FILE_PAGE, blocks)).ordered(blocks)
        return [block.plain_text for block in ordered]

    def test_a_margin_reference_and_footnotes_set_side_by_side_leave_the_page_one_column(self) -> None:
        self.assertEqual(PAGE_ORDER, self._ordered(ENGINE_ORDER))

    def test_a_page_setting_two_columns_of_prose_keeps_the_engines_order(self) -> None:
        self.assertEqual(TWO_COLUMN_ENGINE_ORDER, self._ordered(TWO_COLUMN_ENGINE_ORDER))


if __name__ == "__main__":
    unittest.main()
