from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import PageBlocks
from _extract.layer import TextLayer
from _extract.pagefolios import FolioReader

PAGE_WIDTH = 420.0
PAGE_HEIGHT = 595.0
MARGIN_X = 50.0
HEAD_BASELINE = 40.0
BODY_BASELINE = 90.0
FOOT_BASELINE = 545.0
LINE_SPACING = 14.0
CHAPTER_HEAD = "Title of the Chapter"
APPARATUS_HEAD = "Bibliography"
BODY_TEXT = "Prose of the chapter set on this printed page."
ENTRY_TEXT = "Author, A. (2001) A Work Cited. Place: Publisher."
FIRST_CHAPTER_FOLIO = 63
FIRST_APPARATUS_FOLIO = 228
LONG_RUN = 9
SHORT_RUN = 4
NOTES_PER_PAGE = 2
FIRST_SCATTERED_NOTE = 20
UNNUMBERED_PAGES = 5


@dataclass(frozen=True)
class PrintedPage:
    head: str
    foot: list[str]


def folio_run(first_folio: int, length: int) -> list[str]:
    return [str(first_folio + offset) for offset in range(length)]


def notes_from(first_note: int, count: int) -> list[str]:
    return [f"{first_note + offset} A note on the chapter's argument." for offset in range(count)]


def chapter_pages(length: int) -> list[PrintedPage]:
    return [PrintedPage(f"{CHAPTER_HEAD} {folio}", [BODY_TEXT]) for folio in folio_run(FIRST_CHAPTER_FOLIO, length)]


def annotated_chapter_pages(length: int) -> list[PrintedPage]:
    heads = [CHAPTER_HEAD] + [f"{CHAPTER_HEAD} {folio}" for folio in folio_run(FIRST_CHAPTER_FOLIO, length)]
    return [PrintedPage(head, notes_from(index * NOTES_PER_PAGE + 1, NOTES_PER_PAGE))
            for index, head in enumerate(heads)]


def apparatus_pages(length: int) -> list[PrintedPage]:
    return [PrintedPage(f"{folio} {APPARATUS_HEAD}", [ENTRY_TEXT])
            for folio in folio_run(FIRST_APPARATUS_FOLIO, length)]


def unnumbered_pages_with_notes_a_page_apart() -> list[PrintedPage]:
    return [PrintedPage(APPARATUS_HEAD,
                        notes_from(FIRST_SCATTERED_NOTE + offset, 1) if offset % 2 == 0 else [ENTRY_TEXT])
            for offset in range(UNNUMBERED_PAGES)]


def write_pdf(path: Path, pages: list[PrintedPage]) -> Path:
    with pymupdf.open() as document:
        for printed in pages:
            write_page(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT), printed)
        document.save(path)
    return path


def write_page(page, printed: PrintedPage) -> None:
    page.insert_text((MARGIN_X, HEAD_BASELINE), printed.head)
    page.insert_text((MARGIN_X, BODY_BASELINE), BODY_TEXT)
    for line_number, line in enumerate(printed.foot):
        page.insert_text((MARGIN_X, FOOT_BASELINE + line_number * LINE_SPACING), line)


class FolioCase(unittest.TestCase):
    def folios(self, pages: list[PrintedPage]) -> list[str | None]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(write_pdf(Path(directory.name) / "chapter.pdf", pages))
        self.addCleanup(layer.close)
        blocks = [PageBlocks(file_page, []) for file_page in range(1, len(pages) + 1)]
        return list(FolioReader(layer).of(blocks).values())


class TestBoundInRunAfterTheChapter(FolioCase):
    def test_a_run_shorter_than_the_chapters_keeps_the_folios_it_prints(self) -> None:
        folios = self.folios(chapter_pages(LONG_RUN) + apparatus_pages(SHORT_RUN))
        self.assertEqual(folio_run(FIRST_APPARATUS_FOLIO, SHORT_RUN), folios[LONG_RUN:])

    def test_a_chapter_shorter_than_the_run_keeps_the_folios_it_prints(self) -> None:
        folios = self.folios(chapter_pages(SHORT_RUN) + apparatus_pages(LONG_RUN))
        self.assertEqual(folio_run(FIRST_CHAPTER_FOLIO, SHORT_RUN), folios[:SHORT_RUN])

    def test_a_shorter_chapter_keeps_its_folios_over_note_numbers_advancing_two_per_page(self) -> None:
        folios = self.folios(annotated_chapter_pages(SHORT_RUN) + apparatus_pages(LONG_RUN))
        self.assertEqual([None, *folio_run(FIRST_CHAPTER_FOLIO, SHORT_RUN)], folios[:SHORT_RUN + 1])

    def test_note_numbers_fitting_a_run_on_pages_apart_are_no_folios(self) -> None:
        folios = self.folios(chapter_pages(LONG_RUN) + unnumbered_pages_with_notes_a_page_apart())
        self.assertEqual([None] * UNNUMBERED_PAGES, folios[LONG_RUN:])


if __name__ == "__main__":
    unittest.main()
