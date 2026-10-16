from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

OUTLINE_TITLE = "Between monotone maps and their adjoints"
PRINTED_TITLE = f"B.1 {OUTLINE_TITLE}"
TWO_LEVEL_PRINTED_TITLE = f"B.1.2 {OUTLINE_TITLE}"
CLOSING_PROSE = "and so the appendix section before closes with its last lemma."
OPENING_PROSE = "Let f be a monotone map with an internal left adjoint."
SECTION_LEVEL = 2
SUBLEVEL = 3
LEFT = 72.0
HEADING_SIZE = 12.0
BODY_SIZE = 10.0
ROW_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 16.0
RIGHT = 540.0


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


def rows(printed_title: str) -> list[tuple[str, str]]:
    return [(TEXT_KIND, CLOSING_PROSE), (HEADING_KIND, printed_title), (TEXT_KIND, OPENING_PROSE)]


class AppendixPdf:
    def __init__(self, directory: Path, printed_title: str) -> None:
        self._path = directory / "appendix.pdf"
        self._rows = rows(printed_title)

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, (kind, text) in enumerate(self._rows):
                size = HEADING_SIZE if kind == HEADING_KIND else BODY_SIZE
                page.insert_text((LEFT, _baseline(index)), text, fontsize=size)
            document.save(self._path)
        return self._path


def printed_blocks(printed_title: str) -> PageBlocks:
    return PageBlocks(1, [Block(1, kind, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                          for index, (kind, text) in enumerate(rows(printed_title))])


class TestOutlineTitlesPrintedAfterAnAppendixSubsectionNumber(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _texts(self, printed_title: str) -> list[str]:
        layer = TextLayer(AppendixPdf(self._directory, printed_title).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        due = [OutlineHeading(SECTION_LEVEL, OUTLINE_TITLE, 1)]
        elements = assembler.assemble(printed_blocks(printed_title), due, SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_the_entry_opens_once_where_the_page_prints_its_title_after_the_letter_and_its_number(self) -> None:
        self.assertEqual([CLOSING_PROSE, OUTLINE_TITLE, OPENING_PROSE], self._texts(PRINTED_TITLE))

    def test_the_entry_opens_once_where_the_page_prints_its_title_after_the_letter_and_two_numbers(self) -> None:
        self.assertEqual([CLOSING_PROSE, OUTLINE_TITLE, OPENING_PROSE], self._texts(TWO_LEVEL_PRINTED_TITLE))


if __name__ == "__main__":
    unittest.main()
