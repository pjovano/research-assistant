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

CONTINUED_PROSE = "and so the understanding is driven out of its circle by the demands of reason."
SECTION_NUMBER = "§46"
PRINTED_HEADING = "I. Psychological ideas"
OUTLINE_TITLE = "46 i. Psychological ideas"
OTHER_OUTLINE_TITLE = "46 ii. Cosmological ideas"
OPENING_PROSE = "It has long been observed that in all substances the true subject is unknown to us."
LEVEL = 3
SUBLEVEL = 4
FILE_PAGE = 1
LEFT = 72.0
FONT_SIZE = 10.0
ROW_HEIGHT = 14.0
ROWS = ((TEXT_KIND, CONTINUED_PROSE, 100.0), (HEADING_KIND, SECTION_NUMBER, 140.0),
        (HEADING_KIND, PRINTED_HEADING, 170.0), (TEXT_KIND, OPENING_PROSE, 200.0))


class SectionPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "section.pdf"

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for _kind, text, baseline in ROWS:
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def section_page() -> PageBlocks:
    return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, kind, f"<p>{text}</p>",
                                        (LEFT - 2.0, baseline - ROW_HEIGHT, 540.0, baseline + 4.0), {},
                                        f"/page/1/{index}")
                                  for index, (kind, text, baseline) in enumerate(ROWS)])


class TestOutlineTitlesPrefixingASectionNumberToAHeadingNumberedOnItsOwn(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _written(self, outline_title: str) -> list[str]:
        layer = TextLayer(SectionPagePdf(self._directory).write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(section_page(), [OutlineHeading(LEVEL, outline_title, FILE_PAGE)],
                                      SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_the_entry_opens_once_where_its_heading_prints(self) -> None:
        self.assertEqual([CONTINUED_PROSE, OUTLINE_TITLE, OPENING_PROSE], self._written(OUTLINE_TITLE))

    def test_an_entry_numbering_another_heading_opens_at_its_destination(self) -> None:
        self.assertEqual(OTHER_OUTLINE_TITLE, self._written(OTHER_OUTLINE_TITLE)[0])


if __name__ == "__main__":
    unittest.main()
