from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BoxedLayer, RunSetting, keep_everything, page_assembler, positioned
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.structure import Heading, Paragraph

PROSE_BOX = (0.0, 20.0, 400.0, 60.0)
READ_TWICE_BOX = (0.0, 70.0, 200.0, 84.0)
ENGINE_TWIN_BOX = (0.0, 70.0, 200.0, 85.0)
QUOTED_LINE = "When we say"


def written(twice_read: list[Block]) -> list:
    layer = BoxedLayer(positioned("Body prose.", RunSetting(0.0, 40.0, 0))
                       + positioned(QUOTED_LINE, RunSetting(0.0, 80.0, 1)))
    assembler = page_assembler(layer, keep_everything())
    page = PageBlocks(1, [Block(1, TEXT_KIND, "", PROSE_BOX, {}, "/page/1/Text/0")] + twice_read)
    return [element for element in assembler.assemble(page, [], 2).elements
            if isinstance(element, (Heading, Paragraph))]


class TestRegionsTheEngineReadTwice(unittest.TestCase):
    def test_a_heading_the_engine_also_read_as_empty_text_is_written_once_as_text(self) -> None:
        elements = written([Block(1, HEADING_KIND, f"<h4>{QUOTED_LINE}</h4>", ENGINE_TWIN_BOX, {},
                                  "/page/1/SectionHeader/1"),
                            Block(1, TEXT_KIND, "", READ_TWICE_BOX, {}, "/page/1/Text/2")])
        self.assertEqual([Paragraph("Body prose.", False, 1), Paragraph(QUOTED_LINE, False, 1)], elements)

    def test_text_the_engine_also_read_as_an_empty_heading_is_written_once_as_text(self) -> None:
        elements = written([Block(1, TEXT_KIND, f"<p>{QUOTED_LINE}</p>", ENGINE_TWIN_BOX, {}, "/page/1/Text/1"),
                            Block(1, HEADING_KIND, "", READ_TWICE_BOX, {}, "/page/1/SectionHeader/2")])
        self.assertEqual([Paragraph("Body prose.", False, 1), Paragraph(QUOTED_LINE, False, 1)], elements)


class TestEmptyBlocksInsideARead(unittest.TestCase):
    def test_an_empty_footnote_block_inside_a_read_footnote_leaves_its_lines_to_it_under_the_printed_numerals(
            self) -> None:
        notes = [("19 Taylor, 160.", 80.0, 96.0), ("20 Taylor, 158.", 180.0, 96.0), ("21 Taylor, 159.", 280.0, 96.0),
                 ("22 Taylor, 161.", 80.0, 106.0), ("23 Taylor, 156.", 180.0, 106.0)]
        layer = BoxedLayer([char for row, (text, left, baseline) in enumerate(notes)
                            for char in positioned(text, RunSetting(left, baseline, row))])
        assembler = page_assembler(layer, keep_everything())
        body = "<p>A<sup>19</sup> b<sup>20</sup> c<sup>21</sup> d<sup>22</sup> e<sup>23</sup>.</p>"
        page = PageBlocks(1, [Block(1, TEXT_KIND, body, PROSE_BOX, {}, "/page/1/Text/0"),
                              Block(1, FOOTNOTE_KIND, "<p>19 Taylor, 160.</p>", (78.0, 86.0, 380.0, 110.0), {},
                                    "/page/1/Footnote/1"),
                              Block(1, FOOTNOTE_KIND, "", (76.0, 86.0, 172.0, 99.0), {}, "/page/1/Footnote/2")])
        result = assembler.assemble(page, [], 2)
        self.assertEqual(["[^19]: Taylor, 160.", "[^20]: Taylor, 158.", "[^21]: Taylor, 159.", "[^22]: Taylor, 161.",
                          "[^23]: Taylor, 156."], [definition.rendered() for definition in result.definitions])


if __name__ == "__main__":
    unittest.main()
