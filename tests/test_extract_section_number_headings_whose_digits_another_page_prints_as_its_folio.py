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
from _extract.candidates import RunningHeads
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

CLOSING_PROSE = "and so the usefulness of a system of categories is here revealed clearly."
SECTION_HEADING = "§51"
OUTLINE_TITLE = "51"
FOLIO = "51"
OPENING_PROSE = "In the first place, the antinomy shows that reason is entangled with itself."
LEVEL = 3
SUBLEVEL = 4
FILE_PAGE = 1
LEFT = 72.0
HEADING_LEFT = 200.0
FONT_SIZE = 11.0
ROW_HEIGHT = 14.0
ROWS = ((TEXT_KIND, CLOSING_PROSE, LEFT, 100.0), (HEADING_KIND, SECTION_HEADING, HEADING_LEFT, 140.0),
        (TEXT_KIND, OPENING_PROSE, LEFT, 180.0))


class SectionPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "section.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for _kind, text, left, baseline in ROWS:
                page.insert_text((left, baseline), text, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def section_page() -> PageBlocks:
    return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, kind, f"<p>{text}</p>",
                                        (left - 2.0, baseline - ROW_HEIGHT, 540.0, baseline + 4.0), {},
                                        f"/page/1/{index}")
                                  for index, (kind, text, left, baseline) in enumerate(ROWS)])


class TestSectionNumberHeadingsWhoseDigitsAnotherPagePrintsAsItsFolio(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _written(self, furniture: list[str]) -> list[str]:
        layer = TextLayer(SectionPagePdf(self._directory).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(furniture=furniture))
        elements = assembler.assemble(section_page(), [OutlineHeading(LEVEL, OUTLINE_TITLE, FILE_PAGE)],
                                      SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_the_entry_opens_where_the_section_number_prints(self) -> None:
        self.assertEqual([CLOSING_PROSE, OUTLINE_TITLE, OPENING_PROSE], self._written([FOLIO]))

    def test_a_running_head_printing_the_section_number_still_names_it(self) -> None:
        self.assertTrue(RunningHeads([SECTION_HEADING]).names(SECTION_HEADING))

    def test_the_entry_opens_where_the_section_number_prints_between_text_blocks_a_running_head_repeats(self) -> None:
        self.assertEqual([CLOSING_PROSE, OUTLINE_TITLE, OPENING_PROSE], self._written([SECTION_HEADING]))


if __name__ == "__main__":
    unittest.main()
