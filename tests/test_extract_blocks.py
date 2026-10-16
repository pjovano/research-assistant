from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import Block, DocumentBlocks
from _extract.box import Box
from _extract.layer import LayerChar

UPPER = Box(10.0, 20.0, 110.0, 40.0)
LOWER = Box(30.0, 60.0, 90.0, 80.0)
CONVERTED_FILE_PAGE = 60
UNIT_BOX = [0, 0, 1, 1]
ENGINE_PAYLOAD = {"children": [{"block_type": "Page", "bbox": [0, 0, 10, 10], "children": [
    {"block_type": "PageHeader", "html": "<p>Title 39</p>", "bbox": UNIT_BOX, "id": "/page/0/PageHeader/0"},
    {"block_type": "ListGroup", "html": "", "bbox": UNIT_BOX, "id": "/page/0/ListGroup/1", "children": [
        {"block_type": "ListItem", "html": "<p>one</p>", "bbox": UNIT_BOX, "id": "/page/0/ListItem/2"}]}]}]}


class TestBox(unittest.TestCase):
    def test_a_box_is_read_from_any_four_numbers(self) -> None:
        self.assertEqual(UPPER, Box.of(["10", 20, 110.0, "40"]))

    def test_the_union_spans_every_box(self) -> None:
        self.assertEqual(Box(10.0, 20.0, 110.0, 80.0), Box.union([UPPER, LOWER]))

    def test_center_and_width_read_from_the_edges(self) -> None:
        self.assertEqual(((60.0, 30.0), 100.0), (UPPER.center, UPPER.width))

    def test_a_point_on_the_edge_is_contained(self) -> None:
        self.assertEqual((True, False), (UPPER.contains((10.0, 40.0)), UPPER.contains((10.0, 41.0))))

    def test_a_box_spans_the_rows_it_overlaps(self) -> None:
        self.assertEqual((True, False), (UPPER.spans_rows(35.0, 50.0), UPPER.spans_rows(41.0, 50.0)))

    def test_a_block_and_a_char_built_from_plain_tuples_carry_boxes(self) -> None:
        block = Block(1, "Text", "<p>x</p>", (0, 0, 1, 2), {}, "/page/1/Text/0")
        char = LayerChar("x", (1.0, 1.0), False, 10.0, bbox=(0, 0, 1, 2))
        self.assertEqual((2.0, 2.0), (block.bbox.bottom, char.bbox.bottom))


class TestDocumentBlocks(unittest.TestCase):
    def _page(self):
        return DocumentBlocks.from_json(ENGINE_PAYLOAD, [CONVERTED_FILE_PAGE]).pages[0]

    def test_group_blocks_are_flattened_to_their_leaves(self) -> None:
        self.assertEqual(["PageHeader", "ListItem"], [block.kind for block in self._page().blocks])

    def test_pages_carry_the_file_page_they_were_converted_from(self) -> None:
        self.assertEqual(CONVERTED_FILE_PAGE, self._page().file_page)


if __name__ == "__main__":
    unittest.main()
