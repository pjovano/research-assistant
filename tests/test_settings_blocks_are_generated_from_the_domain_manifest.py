from __future__ import annotations

import json
import unittest

from _domain_settings import (
    DOMAIN_MANIFEST,
    GENERATED_BLOCKS,
    CommittedSettings,
    GeneratedSettings,
    ReadGuards,
    Unordered,
)


class TheCommittedSettingsAreTheGeneratorOutput(unittest.TestCase):
    def setUp(self) -> None:
        self.generated = GeneratedSettings.blocks()
        self.committed = CommittedSettings.blocks()

    def test_the_generator_prints_exactly_the_permissions_and_sandbox_blocks(self) -> None:
        self.assertEqual(set(GENERATED_BLOCKS), set(self.generated))

    def test_each_block_equals_the_generated_block_apart_from_ordering_and_read_guards(self) -> None:
        committed = ReadGuards(self.committed).removed()
        for block in GENERATED_BLOCKS:
            with self.subTest(block=block):
                self.assertEqual(Unordered(committed[block]).canonical(),
                                 Unordered(self.generated[block]).canonical())


class TheCommittedReadGuardsComeInPairs(unittest.TestCase):
    def setUp(self) -> None:
        self.guards = ReadGuards(CommittedSettings.blocks())

    def test_every_guarded_folder_has_both_a_sandbox_denial_and_a_read_rule(self) -> None:
        self.assertEqual(self.guards.sandbox_folders(), self.guards.read_rule_folders())

    def test_no_guarded_folder_is_one_the_domain_lists(self) -> None:
        listed = {folder["name"] for folder in json.loads(DOMAIN_MANIFEST.read_text(encoding="utf-8"))["folders"]}
        self.assertEqual(set(), listed & (self.guards.sandbox_folders() | self.guards.read_rule_folders()))


if __name__ == "__main__":
    unittest.main()
