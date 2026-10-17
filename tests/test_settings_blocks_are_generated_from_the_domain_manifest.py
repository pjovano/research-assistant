from __future__ import annotations

import unittest

from _domain_settings import GENERATED_BLOCKS, CommittedSettings, GeneratedSettings, Unordered


class TheCommittedSettingsAreTheGeneratorOutput(unittest.TestCase):
    def setUp(self) -> None:
        self.committed = CommittedSettings.blocks()
        self.generated = GeneratedSettings.blocks()

    def test_the_generator_prints_exactly_the_permissions_and_sandbox_blocks(self) -> None:
        self.assertEqual(set(GENERATED_BLOCKS), set(self.generated))

    def test_each_block_equals_the_generated_block_apart_from_ordering(self) -> None:
        for block in GENERATED_BLOCKS:
            with self.subTest(block=block):
                self.assertEqual(Unordered(self.generated[block]).canonical(),
                                 Unordered(self.committed[block]).canonical())


if __name__ == "__main__":
    unittest.main()
