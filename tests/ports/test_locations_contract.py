from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeLocations
from _ports.host import Locations
from _rag_fakes import temp_directory

LOCATION_NAMES = ("vault_root", "inbox", "state_dir", "rag_dir")


class LocationsContract:
    def locations(self) -> Locations:
        raise NotImplementedError

    def test_every_location_is_an_absolute_path(self) -> None:
        locations = self.locations()
        for name in LOCATION_NAMES:
            with self.subTest(location=name):
                located = getattr(locations, name)
                self.assertIsInstance(located, Path)
                self.assertTrue(located.is_absolute())

    def test_the_inbox_and_the_state_lie_outside_the_vault(self) -> None:
        locations = self.locations()
        for located in (locations.inbox, locations.state_dir):
            with self.subTest(location=located):
                self.assertFalse(located.is_relative_to(locations.vault_root))


class TestFakeLocationsKeepTheContract(LocationsContract, unittest.TestCase):
    def locations(self) -> Locations:
        return FakeLocations(temp_directory(self))


if __name__ == "__main__":
    unittest.main()
