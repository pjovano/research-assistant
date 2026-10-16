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

PAGE_WIDTH = 420.0
PAGE_HEIGHT = 595.0
MARGIN_X = 50.0
HEAD_BASELINE = 40.0
BODY_BASELINE = 90.0
FOOT_BASELINE = 560.0
HEAD_BOX = (0.0, 28.0, PAGE_WIDTH, 46.0)
FOOT_BOX = (0.0, 548.0, PAGE_WIDTH, 566.0)
PAGE_HEADER_KIND = "PageHeader"
PAGE_FOOTER_KIND = "PageFooter"
RUNNING_HEAD = "Title of the Book"
BODY_TEXT = "Prose of the chapter set on this printed page."
FIRST_FOLIO = 18
RUN_LENGTH = 7
MIDDLE = 3
STRAY_MARKS = ("·", "‘", "*")
STRAY_LETTER = "a"


def write_pdf(path: Path, heads: list[str | None], feet: list[str | None]) -> Path:
    with pymupdf.open() as document:
        for head, foot in zip(heads, feet):
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            if head:
                page.insert_text((MARGIN_X, HEAD_BASELINE), head)
            page.insert_text((MARGIN_X, BODY_BASELINE), BODY_TEXT)
            if foot:
                page.insert_text((MARGIN_X, FOOT_BASELINE), foot)
        document.save(path)
    return path


def furniture_blocks(file_page: int, head: str | None, foot: str | None) -> PageBlocks:
    placed = [(PAGE_HEADER_KIND, head, HEAD_BOX), (PAGE_FOOTER_KIND, foot, FOOT_BOX)]
    return PageBlocks(file_page, [Block(file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{kind}/0")
                                  for kind, text, box in placed if text])


class ChapterOpeningCase(unittest.TestCase):
    def folio_of_the_opening(self, printed_foot: str) -> str | None:
        heads: list[str | None] = [f"{RUNNING_HEAD} {FIRST_FOLIO + offset}" for offset in range(RUN_LENGTH)]
        feet: list[str | None] = [None] * RUN_LENGTH
        heads[MIDDLE], feet[MIDDLE] = None, printed_foot
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(write_pdf(Path(directory.name) / "book.pdf", heads, feet))
        self.addCleanup(layer.close)
        pages = [furniture_blocks(file_page, head, foot)
                 for file_page, (head, foot) in enumerate(zip(heads, feet), start=1)]
        return list(FolioReader(layer).of(pages).values())[MIDDLE]


class TestFoliosBesideAStrayMark(ChapterOpeningCase):
    def test_a_folio_set_after_a_stray_punctuation_mark_is_read(self) -> None:
        folio = str(FIRST_FOLIO + MIDDLE)
        for mark in STRAY_MARKS:
            with self.subTest(mark=mark):
                self.assertEqual(folio, self.folio_of_the_opening(f"{mark}{folio}"))

    def test_a_folio_set_before_a_stray_punctuation_mark_is_read(self) -> None:
        folio = str(FIRST_FOLIO + MIDDLE)
        self.assertEqual(folio, self.folio_of_the_opening(f"{folio}{STRAY_MARKS[0]}"))

    def test_a_number_joined_to_a_letter_is_no_folio(self) -> None:
        self.assertIsNone(self.folio_of_the_opening(f"{STRAY_LETTER}{FIRST_FOLIO + MIDDLE}"))


if __name__ == "__main__":
    unittest.main()
