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

OUTLINE_TITLE = "Supplementary Proofs"
PRINTED_TITLE = f"A {OUTLINE_TITLE}"
CLOSING_PROSE = "and so the list of references closes with the last work it cites."
OPENING_PROSE = "Let f be a monotone map with an internal left adjoint."
SECTION_LEVEL = 1
SUBLEVEL = 2
LEFT = 72.0
HEADING_SIZE = 12.0
BODY_SIZE = 10.0
ROW_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 16.0
RIGHT = 540.0
ROWS = [(TEXT_KIND, CLOSING_PROSE), (HEADING_KIND, PRINTED_TITLE), (TEXT_KIND, OPENING_PROSE)]


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class AppendixPdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "appendix.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, (kind, text) in enumerate(ROWS):
                size = HEADING_SIZE if kind == HEADING_KIND else BODY_SIZE
                page.insert_text((LEFT, _baseline(index)), text, fontsize=size)
            document.save(self._path)
        return self._path


def printed_blocks() -> PageBlocks:
    return PageBlocks(1, [Block(1, kind, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                          for index, (kind, text) in enumerate(ROWS)])


class TestOutlineTitlesPrintedAfterAnAppendixLetter(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(AppendixPdf(directory).write())
        self.addCleanup(self._layer.close)

    def test_the_entry_opens_once_where_the_page_prints_its_title_after_the_letter(self) -> None:
        assembler = page_assembler(self._layer, keep_everything())
        due = [OutlineHeading(SECTION_LEVEL, OUTLINE_TITLE, 1)]
        elements = assembler.assemble(printed_blocks(), due, SUBLEVEL).elements[1:]
        texts = [element.title if isinstance(element, Heading) else element.text for element in elements]
        self.assertEqual([CLOSING_PROSE, OUTLINE_TITLE, OPENING_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
