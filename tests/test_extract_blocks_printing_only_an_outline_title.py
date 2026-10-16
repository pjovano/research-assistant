from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeLayer, keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

SECTION_TITLE = "APPENDIX (FIRST DRAFT)"
CLOSING_PROSE = "The section before closes here."
SECTION_PROSE = "The appendix opens with this sentence."
RUN_IN_TITLE = "2."
RUN_IN_PROSE = "2. The numbered section opens mid-page."
PROSE_PAST_THE_RUN_IN_TITLE = "The numbered section opens mid-page."


def text_block(text: str, top: float, bottom: float) -> Block:
    return Block(1, "Text", f"<p>{text}</p>", (0.0, top, 100.0, bottom), {}, f"/page/1/Text/{top}")


class TestBlocksPrintingOnlyAnOutlineTitle(unittest.TestCase):
    def _texts(self, blocks: list[Block], title: str) -> list[str]:
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), [OutlineHeading(1, title, 1)], 2).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_body_block_printing_only_a_page_top_entrys_title_becomes_its_heading(self) -> None:
        blocks = [text_block(CLOSING_PROSE, 40.0, 120.0), text_block(SECTION_TITLE, 130.0, 142.0),
                  text_block(SECTION_PROSE, 150.0, 300.0)]
        self.assertEqual([CLOSING_PROSE, SECTION_TITLE, SECTION_PROSE], self._texts(blocks, SECTION_TITLE))

    def test_a_body_block_opening_with_a_page_top_entrys_title_gives_the_title_up_to_its_heading(self) -> None:
        blocks = [text_block(CLOSING_PROSE, 40.0, 120.0), text_block(RUN_IN_PROSE, 130.0, 300.0)]
        self.assertEqual([CLOSING_PROSE, RUN_IN_TITLE, PROSE_PAST_THE_RUN_IN_TITLE], self._texts(blocks, RUN_IN_TITLE))


if __name__ == "__main__":
    unittest.main()
