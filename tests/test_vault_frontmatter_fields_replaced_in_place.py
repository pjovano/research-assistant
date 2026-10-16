from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _vault.frontmatter import FrontmatterFields

BLOCK = "---\ntitle: A Work\nsource_type: ''\nfield: []\nyear: 2000\n---\n"


class TestFieldsReplacedInPlace(unittest.TestCase):
    def test_each_field_keeps_its_line_and_every_other_line_is_untouched(self) -> None:
        block = FrontmatterFields().replaced_in_place(BLOCK, {"source_type": "monograph",
                                                               "field": ['"[[Ethics]]"']})
        self.assertEqual("---\ntitle: A Work\nsource_type: monograph\nfield:\n  - \"[[Ethics]]\"\nyear: 2000\n---\n",
                         block)

    def test_a_field_the_block_lacks_is_added_before_the_closing_fence(self) -> None:
        block = FrontmatterFields().replaced_in_place(BLOCK, {"commentary_on": '"[[Spinoza - 1677 - Ethica]]"'})
        self.assertTrue(block.endswith('year: 2000\ncommentary_on: "[[Spinoza - 1677 - Ethica]]"\n---\n'))

    def test_a_sequence_is_replaced_with_its_items(self) -> None:
        listed = "---\nfield:\n  - '[[Old]]'\n  - '[[Older]]'\nyear: 2000\n---\n"
        block = FrontmatterFields().replaced_in_place(listed, {"field": ['"[[New]]"']})
        self.assertEqual('---\nfield:\n  - "[[New]]"\nyear: 2000\n---\n', block)


if __name__ == "__main__":
    unittest.main()
