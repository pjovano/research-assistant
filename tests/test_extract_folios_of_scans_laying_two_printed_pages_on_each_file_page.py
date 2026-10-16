from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import PageBlocks
from _extract.layer import TextLayer
from _extract.pagefolios import FolioReader

SPREAD_WIDTH = 842.0
SPREAD_HEIGHT = 595.0
LEFT_PAGE_X = 60.0
RIGHT_PAGE_X = 490.0
HEAD_BASELINE = 30.0
BODY_BASELINE = 80.0
FIRST_LEFT_FOLIO = 44
PRINTED_PAGES_PER_SPREAD = 2
SPREADS = 5
RUNNING_HEAD = "Author"
RUNNING_TITLE = "Title of the Work"
BODY_TEXT = "Prose of the work set on this printed page."


def left_folios() -> list[str]:
    return [str(FIRST_LEFT_FOLIO + index * PRINTED_PAGES_PER_SPREAD) for index in range(SPREADS)]


class SpreadPdf:
    def __init__(self, path: Path, right_page_prints_its_folio: bool) -> None:
        self._path = path
        self._right_page_prints_its_folio = right_page_prints_its_folio

    def write(self) -> Path:
        with pymupdf.open() as document:
            for left_folio in left_folios():
                self._spread(document.new_page(width=SPREAD_WIDTH, height=SPREAD_HEIGHT), int(left_folio))
            document.save(self._path)
        return self._path

    def _spread(self, page, left_folio: int) -> None:
        page.insert_text((LEFT_PAGE_X, HEAD_BASELINE), f"{left_folio} {RUNNING_HEAD}")
        page.insert_text((RIGHT_PAGE_X, HEAD_BASELINE), self._right_head(left_folio + 1))
        page.insert_text((LEFT_PAGE_X, BODY_BASELINE), BODY_TEXT)
        page.insert_text((RIGHT_PAGE_X, BODY_BASELINE), BODY_TEXT)

    def _right_head(self, right_folio: int) -> str:
        if self._right_page_prints_its_folio:
            return f"{RUNNING_TITLE} {right_folio}"
        return RUNNING_TITLE


class SpreadCase(unittest.TestCase):
    RIGHT_PAGE_PRINTS_ITS_FOLIO = True

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        pdf = SpreadPdf(Path(directory.name) / "spreads.pdf", self.RIGHT_PAGE_PRINTS_ITS_FOLIO).write()
        self.layer = TextLayer(pdf)
        self.addCleanup(self.layer.close)

    def folios(self) -> list[str | None]:
        pages = [PageBlocks(file_page, []) for file_page in range(1, SPREADS + 1)]
        return list(FolioReader(self.layer).of(pages).values())


class TestSpreadsPrintingBothFolios(SpreadCase):
    def test_each_file_page_takes_the_folio_of_its_first_printed_page(self) -> None:
        self.assertEqual(left_folios(), self.folios())


class TestSpreadsPrintingOnlyTheFirstPagesFolio(SpreadCase):
    RIGHT_PAGE_PRINTS_ITS_FOLIO = False

    def test_folios_advancing_by_two_per_file_page_are_read_as_printed(self) -> None:
        self.assertEqual(left_folios(), self.folios())


if __name__ == "__main__":
    unittest.main()
