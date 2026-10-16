from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import HEADER_KIND, WorkFurniture
from _extract.layer import TextLayer

RUNNING_HEAD = "Notes to Chapters Eleven and Twelve"
DIVIDER = "chapter 11: the i think and the for-the-sake-of-which"
NOTE = "1. See the discussion of reflection in the article cited above, pp. 45-67."
BODY_FONT = "helv"
DIVIDER_FONT = "tiro"
SMALL_CAPITALS_NAME = "/Bembo-SC"
ROMAN_NAME = "/Bembo-Roman"
BASE_FONT_KEY = "BaseFont"
LEFT = 72.0
RIGHT = 540.0
FONT_SIZE = 9.0
HEAD_BASELINE = 50.0
DIVIDER_BASELINE = 80.0
NOTE_BASELINE = 110.0
LINE_HEIGHT = 11.0
PAGES = 2


class NotesPagesPdf:
    def __init__(self, directory: Path, divider_font_name: str) -> None:
        self._path = directory / "notes.pdf"
        self._divider_font_name = divider_font_name

    def write(self, divided_pages: set[int]) -> Path:
        with pymupdf.open() as document:
            for file_page in range(1, PAGES + 1):
                self._add_page(document, file_page in divided_pages)
            document.save(self._path)
        return self._path

    def _add_page(self, document, divided: bool) -> None:
        page = document.new_page()
        page.insert_text((LEFT, HEAD_BASELINE), RUNNING_HEAD, fontsize=FONT_SIZE, fontname=BODY_FONT)
        page.insert_text((LEFT, NOTE_BASELINE), NOTE, fontsize=FONT_SIZE, fontname=BODY_FONT)
        if divided:
            page.insert_text((LEFT, DIVIDER_BASELINE), DIVIDER, fontsize=FONT_SIZE, fontname=DIVIDER_FONT)
            divider_font = next(font[0] for font in page.get_fonts() if font[4] == DIVIDER_FONT)
            document.xref_set_key(divider_font, BASE_FONT_KEY, self._divider_font_name)


def _box(baseline: float) -> tuple:
    return (LEFT - 2.0, baseline - LINE_HEIGHT, RIGHT, baseline + 3.0)


def engine_reading(divided_pages: set[int]) -> DocumentBlocks:
    pages = []
    for file_page in range(1, PAGES + 1):
        blocks = [Block(file_page, HEADER_KIND, RUNNING_HEAD, _box(HEAD_BASELINE), {}, f"/page/{file_page}/head")]
        if file_page in divided_pages:
            blocks.append(Block(file_page, HEADER_KIND, DIVIDER, _box(DIVIDER_BASELINE), {}, f"/page/{file_page}/0"))
        blocks.append(Block(file_page, TEXT_KIND, f"<p>{NOTE}</p>", _box(NOTE_BASELINE), {}, f"/page/{file_page}/1"))
        pages.append(PageBlocks(file_page, blocks))
    return DocumentBlocks(pages)


class TestSmallCapitalDividersTheEngineReadsAsAPageHeaderBeneathTheRunningHead(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _divider_kinds(self, divider_font_name: str, divided_pages: set[int]) -> list[str]:
        layer = TextLayer(NotesPagesPdf(self._directory, divider_font_name).write(divided_pages))
        self.addCleanup(layer.close)
        refiled = WorkFurniture(layer).refiled(engine_reading(divided_pages))
        return [block.kind for page in refiled.pages for block in page.blocks if block.plain_text == DIVIDER]

    def test_a_divider_printed_once_in_small_capitals_is_a_heading(self) -> None:
        self.assertEqual([HEADING_KIND], self._divider_kinds(SMALL_CAPITALS_NAME, {1}))

    def test_a_line_printed_once_in_roman_type_stays_furniture(self) -> None:
        self.assertEqual([HEADER_KIND], self._divider_kinds(ROMAN_NAME, {1}))

    def test_a_small_capital_line_repeated_on_every_page_stays_furniture(self) -> None:
        self.assertEqual([HEADER_KIND, HEADER_KIND], self._divider_kinds(SMALL_CAPITALS_NAME, {1, 2}))


if __name__ == "__main__":
    unittest.main()
