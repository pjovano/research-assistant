from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything
from _extract.blocks import FURNITURE_KINDS, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import WorkFurniture
from _extract.headings import HeadingMatch
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.outlineplacement import OutlinePlacement

HEADER_KIND = FURNITURE_KINDS[0]
SECTION_TITLE = "Bibliography"
RUNNING_HEADS = ("286 Bibliography", "Bibliography 287")
NOTE_TEXT = "62. For another view on this, see the chapter by another author in this volume."
ENTRY_TEXT = "Allison, Henry. Kant's Transcendental Idealism. New Haven: Yale University Press, 1983."
NOTES_PAGE = 1
TITLE_PAGE = 2
FONT = "tiro"
TITLE_SIZE = 16.0
RUNNING_HEAD_SIZE = 9.0
TEXT_SIZE = 10.0
LEFT = 72.0
RIGHT = 540.0
HEAD_BASELINE = 60.0
TEXT_BASELINE = 200.0
ROW_HEIGHT = 18.0


class SectionOpeningPages:
    def __init__(self, directory: Path, title_size: float, head_before: tuple[str, float] | None = None) -> None:
        self._path = directory / "section.pdf"
        self._pages = [(head_before, NOTE_TEXT), ((SECTION_TITLE, title_size), ENTRY_TEXT)]
        self._pages += [((head, RUNNING_HEAD_SIZE), ENTRY_TEXT) for head in RUNNING_HEADS]

    def write(self) -> Path:
        with pymupdf.open() as document:
            for head, text in self._pages:
                page = document.new_page()
                if head is not None:
                    page.insert_text((LEFT, HEAD_BASELINE), head[0], fontsize=head[1], fontname=FONT)
                page.insert_text((LEFT, TEXT_BASELINE), text, fontsize=TEXT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([self._page_blocks(number, head, text)
                               for number, (head, text) in enumerate(self._pages, start=1)])

    @staticmethod
    def _page_blocks(file_page: int, head: tuple[str, float] | None, text: str) -> PageBlocks:
        blocks = [Block(file_page, TEXT_KIND, f"<p>{text}</p>", _box(TEXT_BASELINE), {}, f"/page/{file_page}/text")]
        if head is not None:
            blocks.insert(0, Block(file_page, HEADER_KIND, f"<p>{head[0]}</p>", _box(HEAD_BASELINE), {},
                                   f"/page/{file_page}/head"))
        return PageBlocks(file_page, blocks)


def _box(baseline: float) -> tuple:
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestPageHeadersInDisplayTypeOpeningTheRunningHeadsThatRepeatThem(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _refiled(self, title_size: float, head_before: tuple[str, float] | None = None) -> DocumentBlocks:
        pages = SectionOpeningPages(self._directory, title_size, head_before)
        layer = TextLayer(pages.write())
        self.addCleanup(layer.close)
        return WorkFurniture(layer).refiled(pages.blocks)

    def _header_kinds(self, title_size: float) -> list[str]:
        return [page.blocks[0].kind for page in self._refiled(title_size).pages[1:]]

    def test_the_header_set_larger_becomes_a_heading_and_the_running_heads_stay_furniture(self) -> None:
        self.assertEqual([HEADING_KIND, HEADER_KIND, HEADER_KIND], self._header_kinds(TITLE_SIZE))

    def test_a_header_set_in_the_running_heads_type_stays_furniture(self) -> None:
        self.assertEqual([HEADER_KIND] * 3, self._header_kinds(RUNNING_HEAD_SIZE))

    def test_a_larger_header_after_a_page_printing_its_words_as_a_running_head_stays_furniture(self) -> None:
        refiled = self._refiled(TITLE_SIZE, (RUNNING_HEADS[0], RUNNING_HEAD_SIZE))
        self.assertEqual([HEADER_KIND] * 4, [page.blocks[0].kind for page in refiled.pages])

    def test_an_outline_entry_anchored_a_page_early_moves_to_the_page_printing_the_larger_header(self) -> None:
        placed = OutlinePlacement(self._refiled(TITLE_SIZE).pages, HeadingMatch(), keep_everything()).placed(
            [OutlineHeading(1, SECTION_TITLE, NOTES_PAGE)])
        self.assertEqual([TITLE_PAGE], [heading.file_page for heading in placed])


if __name__ == "__main__":
    unittest.main()
