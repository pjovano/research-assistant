from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace, FakeLayer, PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

HEADER_KIND = "PageHeader"
FONT_SIZE = 10.0
TEXT_LEFT = 72.0
NUMBER_LEFT = 280.0
MARGIN_LEFT = 20.0
HEAD_NUMBER = "6"
SECTION_NUMBER = "7"
CLOSING_PROSE = "and so the argument of the section before comes to its close."
OPENING_PROSE = "The argument of the next section starts from a charge of confusion."
HEAD_BOX = (278.0, 40.0, 290.0, 54.0)
CLOSING_BOX = (70.0, 66.0, 500.0, 100.0)
NUMBER_BOX = (278.0, 120.0, 290.0, 134.0)
MARGIN_BOX = (18.0, 120.0, 30.0, 134.0)
OPENING_BOX = (70.0, 146.0, 500.0, 180.0)


class NumberedSectionPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for left, baseline, text in ((NUMBER_LEFT, 52.0, HEAD_NUMBER), (TEXT_LEFT, 80.0, CLOSING_PROSE),
                                         (NUMBER_LEFT, 132.0, SECTION_NUMBER), (MARGIN_LEFT, 132.0, SECTION_NUMBER),
                                         (TEXT_LEFT, 160.0, OPENING_PROSE)):
                page.insert_text((left, baseline), text, fontname="helv", fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def block(kind: str, text: str, place: BlockPlace) -> Block:
    return place.block(kind, f"<p>{text}</p>")


def page_with(number_block: Block) -> PageBlocks:
    return PageBlocks(1, [block(HEADER_KIND, HEAD_NUMBER, BlockPlace(HEAD_BOX, 0)),
                          block(TEXT_KIND, CLOSING_PROSE, BlockPlace(CLOSING_BOX, 1)),
                          number_block, block(TEXT_KIND, OPENING_PROSE, BlockPlace(OPENING_BOX, 3))])


class TestAPageHeaderStandingBetweenTextBlocks(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(NumberedSectionPdf(directory / "numbered.pdf").write())
        self.addCleanup(self._layer.close)

    def _refiled_kinds(self, number_box: tuple) -> list[str]:
        page = page_with(block(HEADER_KIND, SECTION_NUMBER, BlockPlace(number_box, 2)))
        return [kept.kind for kept in WorkFurniture(self._layer).refiled(DocumentBlocks([page])).pages[0].blocks]

    def test_a_page_header_standing_between_two_text_blocks_in_their_column_is_a_heading(self) -> None:
        self.assertEqual(HEADING_KIND, self._refiled_kinds(NUMBER_BOX)[2])

    def test_a_page_header_above_the_text_stays_furniture(self) -> None:
        self.assertEqual(HEADER_KIND, self._refiled_kinds(NUMBER_BOX)[0])

    def test_a_page_header_in_the_margin_beside_the_text_stays_furniture(self) -> None:
        self.assertEqual(HEADER_KIND, self._refiled_kinds(MARGIN_BOX)[2])


class TestAHeadingNamingAFurnitureTextBetweenTextBlocks(unittest.TestCase):
    def _texts(self, blocks: list[Block], due: list[OutlineHeading]) -> list[str]:
        assembler = page_assembler(FakeLayer(), keep_everything(), PrintedWork(furniture=[SECTION_NUMBER]))
        elements = assembler.assemble(PageBlocks(1, blocks), due, None).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_it_opens_its_outline_entry_where_the_page_prints_it(self) -> None:
        blocks = [block(TEXT_KIND, CLOSING_PROSE, BlockPlace(CLOSING_BOX, 0)),
                  block(HEADING_KIND, SECTION_NUMBER, BlockPlace(NUMBER_BOX, 1)),
                  block(TEXT_KIND, OPENING_PROSE, BlockPlace(OPENING_BOX, 2))]
        texts = self._texts(blocks, [OutlineHeading(1, SECTION_NUMBER, 1)])
        self.assertEqual([CLOSING_PROSE, SECTION_NUMBER, OPENING_PROSE], texts)

    def test_one_above_the_text_is_still_furniture(self) -> None:
        blocks = [block(HEADING_KIND, SECTION_NUMBER, BlockPlace(HEAD_BOX, 0)),
                  block(TEXT_KIND, CLOSING_PROSE, BlockPlace(CLOSING_BOX, 1))]
        self.assertEqual([CLOSING_PROSE], self._texts(blocks, []))


if __name__ == "__main__":
    unittest.main()
