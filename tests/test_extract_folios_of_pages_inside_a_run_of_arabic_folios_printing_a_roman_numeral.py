from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
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
HEAD_BOX = (0.0, 28.0, PAGE_WIDTH, 46.0)
PAGE_HEADER_KIND = "PageHeader"
RUNNING_HEAD = "Title of the Book"
BODY_TEXT = "Prose of the chapter set on this printed page."
FIRST_FOLIO = 8
RUN_LENGTH = 7
MIDDLE = 3
CHAPTER_NUMERAL = "III"
FRONT_MATTER_FOLIO = "vii"


@dataclass(frozen=True)
class PrintedPage:
    drawn_head: str
    read_head: str | None

    @classmethod
    def numbered(cls, folio: int) -> PrintedPage:
        head = f"{RUNNING_HEAD} {folio}"
        return cls(head, head)


def run_with_middle_page(middle: PrintedPage) -> list[PrintedPage]:
    pages = [PrintedPage.numbered(FIRST_FOLIO + offset) for offset in range(RUN_LENGTH)]
    pages[MIDDLE] = middle
    return pages


def write_pdf(path: Path, pages: list[PrintedPage]) -> Path:
    with pymupdf.open() as document:
        for printed in pages:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((MARGIN_X, HEAD_BASELINE), printed.drawn_head)
            page.insert_text((MARGIN_X, BODY_BASELINE), BODY_TEXT)
        document.save(path)
    return path


def engine_blocks(file_page: int, printed: PrintedPage) -> PageBlocks:
    if printed.read_head is None:
        return PageBlocks(file_page, [])
    html = f"<p>{printed.read_head}</p>"
    return PageBlocks(file_page, [Block(file_page, PAGE_HEADER_KIND, html, HEAD_BOX, {},
                                        f"/page/{file_page}/{PAGE_HEADER_KIND}/0")])


class RunCase(unittest.TestCase):
    def folios(self, pages: list[PrintedPage]) -> list[str | None]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(write_pdf(Path(directory.name) / "book.pdf", pages))
        self.addCleanup(layer.close)
        blocks = [engine_blocks(file_page, printed) for file_page, printed in enumerate(pages, start=1)]
        return list(FolioReader(layer).of(blocks).values())


class TestRomanNumeralsInsideARunOfArabicFolios(RunCase):
    def test_a_chapter_numeral_atop_a_page_printing_no_folio_is_not_its_folio(self) -> None:
        folios = self.folios(run_with_middle_page(PrintedPage(CHAPTER_NUMERAL, None)))
        self.assertIsNone(folios[MIDDLE])

    def test_a_running_head_read_as_roman_letters_gives_way_to_the_text_layers_folio_in_the_run(self) -> None:
        folio = str(FIRST_FOLIO + MIDDLE)
        folios = self.folios(run_with_middle_page(PrintedPage(folio, folio.replace("1", "I"))))
        self.assertEqual(folio, folios[MIDDLE])

    def test_a_roman_folio_on_a_page_before_the_run_is_kept(self) -> None:
        front_matter = PrintedPage(FRONT_MATTER_FOLIO, FRONT_MATTER_FOLIO)
        folios = self.folios([front_matter] + run_with_middle_page(PrintedPage.numbered(FIRST_FOLIO + MIDDLE)))
        self.assertEqual(FRONT_MATTER_FOLIO, folios[0])


if __name__ == "__main__":
    unittest.main()
