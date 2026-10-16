from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import Block, PageBlocks
from _extract.layer import TextLayer
from _extract.pagefolios import FolioReader

FONT = "tiro"
TEXT_SIZE = 8.0
NOTE_NUMBER_SIZE = 6.8
NOTE_NUMBER_RISE = 2.9
LEFT = 50.0
NOTE_TEXT_LEFT = 60.0
HEADER_BASELINE = 40.0
BODY_BASELINE = 100.0
FIRST_NOTE_BASELINE = 580.0
NOTE_PITCH = 12.0
TEXT_KIND = "Text"
BODY_BOX = (0.0, 86.0, 600.0, 106.0)
RUNNING_HEAD = "Journal"
BODY_TEXT = "Prose of the article on this page, which prints no folio."
FIRST_NOTE_NUMBER = 11
NOTES_PER_PAGE = 2
PAGE_COUNT = 4


class FootnotedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            for index in range(PAGE_COUNT):
                self._page(document.new_page(), FIRST_NOTE_NUMBER + index * NOTES_PER_PAGE)
            document.save(self._path)
        return self._path

    def _page(self, page, first_note: int) -> None:
        page.insert_text((LEFT, HEADER_BASELINE), RUNNING_HEAD, fontsize=TEXT_SIZE, fontname=FONT)
        page.insert_text((LEFT, BODY_BASELINE), BODY_TEXT, fontsize=TEXT_SIZE, fontname=FONT)
        for position in range(NOTES_PER_PAGE):
            self._note(page, first_note + position, FIRST_NOTE_BASELINE + position * NOTE_PITCH)

    @staticmethod
    def _note(page, number: int, baseline: float) -> None:
        page.insert_text((LEFT, baseline - NOTE_NUMBER_RISE), str(number), fontsize=NOTE_NUMBER_SIZE, fontname=FONT)
        page.insert_text((NOTE_TEXT_LEFT, baseline), "See the work cited above.", fontsize=TEXT_SIZE, fontname=FONT)


def body_page(file_page: int) -> PageBlocks:
    return PageBlocks(file_page, [Block(file_page, TEXT_KIND, f"<p>{BODY_TEXT}</p>", BODY_BOX, {},
                                        f"/page/{file_page}/{TEXT_KIND}/0")])


class TestFoliosOfPagesEndingOnFootnotesOpeningWithARaisedNumber(unittest.TestCase):
    def test_a_raised_note_number_at_the_page_foot_is_no_folio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layer = TextLayer(FootnotedPdf(Path(directory) / "article.pdf").write())
            try:
                folios = FolioReader(layer).of([body_page(page) for page in range(1, PAGE_COUNT + 1)])
            finally:
                layer.close()
        self.assertEqual([None] * PAGE_COUNT, list(folios.values()))


if __name__ == "__main__":
    unittest.main()
