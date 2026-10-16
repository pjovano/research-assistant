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
HEAD_BOX = (0.0, 28.0, PAGE_WIDTH, 46.0)
PAGE_HEADER_KIND = "PageHeader"
CHAPTER_HEAD = "Title of the Chapter"
APPARATUS_HEAD = "General Bibliography"
BODY_TEXT = "Prose of the chapter set on this printed page."
FIRST_CHAPTER_FOLIO = 63
FIRST_APPARATUS_FOLIO = 297
CHAPTER_RUN = 9
TWO_PAGE_RUN = 2
UNNUMBERED_PAGE = [None]


def folio_run(first_folio: int, length: int) -> list[str]:
    return [str(first_folio + offset) for offset in range(length)]


def heads(chapter_run: int, apparatus_run: int) -> list[str | None]:
    chapter = [f"{CHAPTER_HEAD} {folio}" for folio in folio_run(FIRST_CHAPTER_FOLIO, chapter_run)]
    apparatus = [f"{APPARATUS_HEAD} {folio}" for folio in folio_run(FIRST_APPARATUS_FOLIO, apparatus_run)]
    return chapter + UNNUMBERED_PAGE + apparatus


def write_pdf(path: Path, page_heads: list[str | None]) -> Path:
    with pymupdf.open() as document:
        for head in page_heads:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            if head:
                page.insert_text((MARGIN_X, HEAD_BASELINE), head)
            page.insert_text((MARGIN_X, BODY_BASELINE), BODY_TEXT)
        document.save(path)
    return path


def running_head_blocks(file_page: int, head: str | None) -> PageBlocks:
    if head is None:
        return PageBlocks(file_page, [])
    block = Block(file_page, PAGE_HEADER_KIND, f"<p>{head}</p>", HEAD_BOX, {}, f"/page/{file_page}/PageHeader/0")
    return PageBlocks(file_page, [block])


def unread_blocks(file_page: int, _head: str | None) -> PageBlocks:
    return PageBlocks(file_page, [])


class TwoPageRunCase(unittest.TestCase):
    def folios(self, page_heads: list[str | None], blocks_of) -> list[str | None]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(write_pdf(Path(directory.name) / "chapter.pdf", page_heads))
        self.addCleanup(layer.close)
        pages = [blocks_of(file_page, head) for file_page, head in enumerate(page_heads, start=1)]
        return list(FolioReader(layer).of(pages).values())


class TestTwoPageRunAfterTheChapter(TwoPageRunCase):
    def test_a_two_page_run_the_running_head_and_the_text_layer_both_read_keeps_its_folios(self) -> None:
        folios = self.folios(heads(CHAPTER_RUN, TWO_PAGE_RUN), running_head_blocks)
        self.assertEqual(folio_run(FIRST_APPARATUS_FOLIO, TWO_PAGE_RUN), folios[-TWO_PAGE_RUN:])

    def test_a_two_page_run_only_the_text_layer_reads_carries_no_folio(self) -> None:
        folios = self.folios(heads(CHAPTER_RUN, TWO_PAGE_RUN), unread_blocks)
        self.assertEqual([None] * TWO_PAGE_RUN, folios[-TWO_PAGE_RUN:])

    def test_a_single_page_the_running_head_and_the_text_layer_both_read_carries_no_folio(self) -> None:
        folios = self.folios(heads(CHAPTER_RUN, 1), running_head_blocks)
        self.assertEqual([None], folios[-1:])


if __name__ == "__main__":
    unittest.main()
