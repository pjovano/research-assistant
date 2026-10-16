from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeSystemReadings
from _ports.host import Level, SystemReadings

SWAP_IN_USE_BYTES = 2 * 1024 ** 3


class SystemReadingsContract:
    def readings(self) -> SystemReadings:
        raise NotImplementedError

    def test_the_memory_pressure_is_read_on_the_one_scale(self) -> None:
        self.assertIsInstance(self.readings().memory_pressure(), Level)

    def test_the_thermal_state_is_read_on_the_one_scale(self) -> None:
        self.assertIsInstance(self.readings().thermal(), Level)

    def test_the_swap_in_use_is_a_whole_number_of_bytes_never_below_zero(self) -> None:
        swap = self.readings().swap_used()
        self.assertIsInstance(swap, int)
        self.assertGreaterEqual(swap, 0)


class TestFakeSystemReadingsKeepTheContract(SystemReadingsContract, unittest.TestCase):
    def readings(self) -> SystemReadings:
        return FakeSystemReadings(Level.ELEVATED, Level.SERIOUS, SWAP_IN_USE_BYTES)


if __name__ == "__main__":
    unittest.main()
