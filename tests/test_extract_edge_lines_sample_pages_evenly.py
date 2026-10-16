from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.edgelines import evenly


class TestEvenSample(unittest.TestCase):
    def test_a_sample_spans_the_first_and_the_last_page(self) -> None:
        self.assertEqual([1, 5, 10], evenly(list(range(1, 11)), 3))

    def test_a_sample_larger_than_its_pages_takes_them_all(self) -> None:
        self.assertEqual([4, 8], evenly([4, 8], 5))

    def test_a_sample_of_one_takes_the_middle_page(self) -> None:
        self.assertEqual([3], evenly([1, 2, 3, 4, 5], 1))


if __name__ == "__main__":
    unittest.main()
