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

OUTLINE_TITLE = "3. Clusters between Patterns. Structurally Non-Connected Sets"
PRINTED_TITLE = "3. Clusters between patterns (cf. Figure 4)"
PARENT_TITLE = "5.6.3 Contextual Observables and Physical Quantities"
SUBSECTION_TITLE = "5.6.3.1 Contextual Observables"
CARRIED_PROSE = "and so the definition of a cocone carried over from the page before comes to its end."
OPENING_PROSE = "If P and Q are two patterns in a category, a cluster from P to Q is a maximal set of morphisms."
SECTION_LEVEL = 2
SUBLEVEL = 3
LEFT = 72.0
HEADING_SIZE = 12.0
BODY_SIZE = 10.0
ROW_PITCH = 40.0
FIRST_BASELINE = 80.0
ROW_HEIGHT = 16.0
RIGHT = 540.0


class PrintedRows:
    def __init__(self, directory: Path, rows: list[tuple[str, str]]) -> None:
        self._path = directory / "sections.pdf"
        self._rows = rows

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, (kind, text) in enumerate(self._rows):
                size = HEADING_SIZE if kind == HEADING_KIND else BODY_SIZE
                page.insert_text((LEFT, _baseline(index)), text, fontsize=size)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(1, [Block(1, kind, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                              for index, (kind, text) in enumerate(self._rows)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestHeadingsToldApartByTheirSectionNumbers(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _texts(self, rows: list[tuple[str, str]], due: list[OutlineHeading]) -> list[str]:
        printed = PrintedRows(self._directory, rows)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(printed.blocks, due, SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_an_outline_title_worded_otherwise_than_the_heading_printing_its_number_opens_there_once(self) -> None:
        rows = [(TEXT_KIND, CARRIED_PROSE), (HEADING_KIND, PRINTED_TITLE), (TEXT_KIND, OPENING_PROSE)]
        texts = self._texts(rows, [OutlineHeading(SECTION_LEVEL, OUTLINE_TITLE, 1)])
        self.assertEqual([CARRIED_PROSE, OUTLINE_TITLE, OPENING_PROSE], texts)

    def test_a_subsection_whose_words_open_its_parents_title_opens_its_own_heading(self) -> None:
        rows = [(HEADING_KIND, PARENT_TITLE), (TEXT_KIND, CARRIED_PROSE), (HEADING_KIND, SUBSECTION_TITLE),
                (TEXT_KIND, OPENING_PROSE)]
        texts = self._texts(rows, [OutlineHeading(SECTION_LEVEL, PARENT_TITLE, 1)])
        self.assertEqual([PARENT_TITLE, CARRIED_PROSE, SUBSECTION_TITLE, OPENING_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
