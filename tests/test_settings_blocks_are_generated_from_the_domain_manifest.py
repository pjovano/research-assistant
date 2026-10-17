from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _domain_settings import (
    GENERATED_BLOCKS,
    LEDGER_MANIFEST,
    CommittedSettings,
    GeneratedSettings,
    ReadGuards,
    RegeneratedSettings,
    Unordered,
)

LEDGER_SENSITIVE_FOLDER_THE_DOMAIN_LACKS = "taxes"


class TheCommittedSettingsAreTheGeneratorOutputForTheirReadGuards(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.committed = CommittedSettings.blocks()
        self.regenerated = RegeneratedSettings(self.committed, directory).blocks()

    def test_the_generator_prints_exactly_the_permissions_and_sandbox_blocks(self) -> None:
        self.assertEqual(set(GENERATED_BLOCKS), set(self.regenerated))

    def test_each_block_equals_the_generated_block_apart_from_ordering(self) -> None:
        for block in GENERATED_BLOCKS:
            with self.subTest(block=block):
                self.assertEqual(Unordered(self.committed[block]).canonical(),
                                 Unordered(self.regenerated[block]).canonical())


class TheRegeneratedBlocksCatchAHandEditedReadGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.guarded = GeneratedSettings((LEDGER_MANIFEST,)).blocks()

    def test_a_sensitive_folder_another_domain_lists_gets_both_halves_of_a_read_guard(self) -> None:
        guards = ReadGuards(self.guarded)
        self.assertEqual(({LEDGER_SENSITIVE_FOLDER_THE_DOMAIN_LACKS}, {LEDGER_SENSITIVE_FOLDER_THE_DOMAIN_LACKS}),
                         (guards.sandbox_folders(), guards.read_rule_folders()))

    def test_generated_blocks_equal_the_blocks_regenerated_for_their_read_guards(self) -> None:
        regenerated = RegeneratedSettings(self.guarded, self.directory).blocks()
        self.assertEqual(Unordered(self.guarded).canonical(), Unordered(regenerated).canonical())

    def test_a_read_guard_missing_its_read_rule_differs_from_the_regenerated_blocks(self) -> None:
        unpaired = ReadGuards(self.guarded).without_read_rules()
        regenerated = RegeneratedSettings(unpaired, self.directory).blocks()
        self.assertNotEqual(Unordered(unpaired).canonical(), Unordered(regenerated).canonical())


if __name__ == "__main__":
    unittest.main()
