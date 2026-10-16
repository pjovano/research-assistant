from __future__ import annotations

import typing
import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeAccelerator
from _ports.host import Accelerator, Device

DEVICES = typing.get_args(Device)


class AcceleratorContract:
    def accelerator(self) -> Accelerator:
        raise NotImplementedError

    def test_the_device_is_one_the_engines_know(self) -> None:
        self.assertIn(self.accelerator().device(), DEVICES)

    def test_reachable_answers_nothing_or_a_stated_failure(self) -> None:
        failure = self.accelerator().reachable()
        if failure is not None:
            self.assertTrue(failure.strip())


class TestFakeAcceleratorKeepsTheContract(AcceleratorContract, unittest.TestCase):
    def accelerator(self) -> Accelerator:
        return FakeAccelerator("cpu")


class TestAFailingFakeAcceleratorKeepsTheContract(AcceleratorContract, unittest.TestCase):
    def accelerator(self) -> Accelerator:
        return FakeAccelerator("mps", "the process has no Metal")


if __name__ == "__main__":
    unittest.main()
