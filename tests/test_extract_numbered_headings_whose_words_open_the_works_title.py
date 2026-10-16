from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading

WORK_TITLE = "Natural Transformations"
NUMBERED_HEADING = "6.2 Natural Transformations: The Folklore"
ROMAN_NUMBERED_HEADING = "III. Natural Transformations"
UNNUMBERED_HEADING = "Natural Transformations"
PROSE = "A natural transformation is said to be defined without any arbitrary choice of components."
LEFT = 72.0
HEADING_SIZE = 12.0
BODY_SIZE = 10.0
HEADING_BASELINE = 100.0
PROSE_BASELINE = 130.0
HEADING_BOX = (70.0, 86.0, 400.0, 104.0)
PROSE_BOX = (70.0, 120.0, 540.0, 134.0)


class SectionPagePdf:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(self, heading: str) -> Path:
        path = self._directory / "section.pdf"
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, HEADING_BASELINE), heading, fontsize=HEADING_SIZE)
            page.insert_text((LEFT, PROSE_BASELINE), PROSE, fontsize=BODY_SIZE)
            document.save(path)
        return path


def section_page(heading: str) -> PageBlocks:
    return PageBlocks(1, [Block(1, HEADING_KIND, f"<h2>{heading}</h2>", HEADING_BOX, {}, "/page/1/0"),
                          Block(1, TEXT_KIND, f"<p>{PROSE}</p>", PROSE_BOX, {}, "/page/1/1")])


class TestNumberedHeadingsWhoseWordsOpenTheWorksTitle(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _headings(self, heading: str) -> list[str]:
        layer = TextLayer(SectionPagePdf(self._directory).write(heading))
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(work_title=WORK_TITLE))
        elements = assembler.assemble(section_page(heading), [], 2).elements
        return [element.title for element in elements if isinstance(element, Heading)]

    def test_a_heading_numbered_as_a_subsection_opens_a_section_though_its_words_open_the_works_title(self) -> None:
        self.assertEqual([NUMBERED_HEADING], self._headings(NUMBERED_HEADING))

    def test_a_heading_numbered_with_a_roman_numeral_and_a_period_opens_a_section(self) -> None:
        self.assertEqual([ROMAN_NUMBERED_HEADING], self._headings(ROMAN_NUMBERED_HEADING))

    def test_an_unnumbered_line_opening_the_works_title_is_still_dropped_as_its_running_head(self) -> None:
        self.assertEqual([], self._headings(UNNUMBERED_HEADING))


if __name__ == "__main__":
    unittest.main()
