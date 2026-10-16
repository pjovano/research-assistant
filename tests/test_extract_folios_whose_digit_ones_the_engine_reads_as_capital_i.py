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
RUN_LENGTH = 7
FRONT_MATTER_FOLIO = "viii"
FIRST_PAGE_OF_THE_BOOK = "1"
JOURNAL_RUN_FIRST_FOLIO = 428
MIDDLE = 3
FOLIO_SPLIT_BEFORE_ITS_LAST_ONE = "43 I"
FOLIO_READ_WITH_A_CAPITAL_I = "2I"
DIGIT_FOLIO_TOO_FEW_TO_ELECT_A_FIRST_RUN = ("22",)
DIGIT_FOLIOS_TOO_FEW_TO_ELECT_A_LATER_RUN = ("22", "23")


@dataclass(frozen=True)
class PrintedPage:
    drawn_head: str | None
    read_head: str | None

    @classmethod
    def numbered(cls, folio: int) -> PrintedPage:
        head = f"{RUNNING_HEAD} {folio}"
        return cls(head, head)

    @classmethod
    def read_only_by_the_engine(cls, reading: str) -> PrintedPage:
        return cls(None, reading)


def numbered_run(first_folio: int) -> list[PrintedPage]:
    return [PrintedPage.numbered(first_folio + offset) for offset in range(RUN_LENGTH)]


def write_pdf(path: Path, pages: list[PrintedPage]) -> Path:
    with pymupdf.open() as document:
        for printed in pages:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            if printed.drawn_head:
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


class ScannedRunCase(unittest.TestCase):
    def folios(self, pages: list[PrintedPage]) -> list[str | None]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(write_pdf(Path(directory.name) / "scan.pdf", pages))
        self.addCleanup(layer.close)
        blocks = [engine_blocks(file_page, printed) for file_page, printed in enumerate(pages, start=1)]
        return list(FolioReader(layer).of(blocks).values())


class TestDigitOnesReadAsCapitalI(ScannedRunCase):
    def test_the_first_folio_of_a_run_read_as_a_capital_i_is_the_folio_the_run_predicts(self) -> None:
        front_matter = PrintedPage(FRONT_MATTER_FOLIO, FRONT_MATTER_FOLIO)
        opening = PrintedPage.read_only_by_the_engine(FIRST_PAGE_OF_THE_BOOK.replace("1", "I"))
        folios = self.folios([front_matter, opening] + numbered_run(int(FIRST_PAGE_OF_THE_BOOK) + 1))
        self.assertEqual(FIRST_PAGE_OF_THE_BOOK, folios[1])

    def test_a_folio_whose_last_one_is_read_as_a_capital_i_apart_from_its_digits_is_the_whole_folio(self) -> None:
        pages = numbered_run(JOURNAL_RUN_FIRST_FOLIO)
        pages[MIDDLE] = PrintedPage.read_only_by_the_engine(FOLIO_SPLIT_BEFORE_ITS_LAST_ONE)
        self.assertEqual(str(JOURNAL_RUN_FIRST_FOLIO + MIDDLE), self.folios(pages)[MIDDLE])

    def test_a_capital_i_read_as_a_one_casts_no_vote_for_the_first_run(self) -> None:
        readings = [FOLIO_READ_WITH_A_CAPITAL_I, *DIGIT_FOLIO_TOO_FEW_TO_ELECT_A_FIRST_RUN]
        pages = [PrintedPage.read_only_by_the_engine(reading) for reading in readings]
        self.assertEqual([None] * len(pages), self.folios(pages))

    def test_a_capital_i_read_as_a_one_casts_no_vote_for_a_later_run(self) -> None:
        readings = [FOLIO_READ_WITH_A_CAPITAL_I, *DIGIT_FOLIOS_TOO_FEW_TO_ELECT_A_LATER_RUN]
        later = [PrintedPage.read_only_by_the_engine(reading) for reading in readings]
        pages = numbered_run(JOURNAL_RUN_FIRST_FOLIO) + [PrintedPage(None, None)] + later
        self.assertEqual([None] * len(later), self.folios(pages)[-len(later):])


if __name__ == "__main__":
    unittest.main()
