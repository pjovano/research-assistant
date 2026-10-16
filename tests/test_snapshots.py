from __future__ import annotations

import unittest

from _goldencase import GoldenTestCase
from _support import LiveTree

LiveTree.activate()

from _snapshots import BuildItemSnapshot, NamingEdgeCaseSnapshot, NamingSnapshot


class TestVaultNaming(GoldenTestCase):
    def test_naming_over_the_frozen_corpus_is_unchanged(self) -> None:
        self.assert_matches_golden(NamingSnapshot())


class TestVaultNamingEdgeCases(GoldenTestCase):
    def test_hand_picked_edge_cases_are_unchanged(self) -> None:
        self.assert_matches_golden(NamingEdgeCaseSnapshot())


class TestZoteroBuildItem(GoldenTestCase):
    def test_built_items_over_the_frozen_corpus_are_unchanged(self) -> None:
        self.assert_matches_golden(BuildItemSnapshot())


if __name__ == "__main__":
    unittest.main()
