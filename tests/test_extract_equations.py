from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BBOX, FakeLayer, keep_everything, page_assembler
from _extract.blocks import EQUATION_KIND, Block, PageBlocks


class TestEmptyEquation(unittest.TestCase):
    def test_an_equation_block_with_no_text_contributes_nothing(self) -> None:
        assembler = page_assembler(FakeLayer(), keep_everything())
        empty = Block(1, EQUATION_KIND, "", BBOX, {}, "/page/1/Equation/0")
        self.assertEqual(1, len(assembler.assemble(PageBlocks(1, [empty]), [], 1).elements))


if __name__ == "__main__":
    unittest.main()
