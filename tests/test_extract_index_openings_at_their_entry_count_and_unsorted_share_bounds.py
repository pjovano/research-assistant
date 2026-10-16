from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.firstlines import MAX_UNSORTED_SHARE, MIN_INDEX_ENTRIES, FirstLines

INDEX_HEADING = "Index"
SORTED_NAMES = ("Aristotle", "Brentano", "Carnap", "Descartes", "Euclid", "Frege", "Galen")
PAGE_REFERENCE = "12, 40-41"
SAMPLED_ENTRIES = 5


def index_page(names: list[str]) -> FirstLines:
    return FirstLines([INDEX_HEADING] + [f"{name}, {PAGE_REFERENCE}" for name in names])


def entries_with_descents(descents: int) -> list[str]:
    names = list(SORTED_NAMES[:SAMPLED_ENTRIES])
    for pair in range(descents):
        first = 2 * pair
        names[first], names[first + 1] = names[first + 1], names[first]
    return names


class TestIndexOpeningsAtTheMinimumEntryCount(unittest.TestCase):
    def test_a_page_listing_one_entry_fewer_than_the_minimum_opens_no_index(self) -> None:
        self.assertFalse(index_page(list(SORTED_NAMES[:MIN_INDEX_ENTRIES - 1])).opens_an_index())

    def test_a_page_listing_the_minimum_number_of_entries_opens_an_index(self) -> None:
        self.assertTrue(index_page(list(SORTED_NAMES[:MIN_INDEX_ENTRIES])).opens_an_index())


class TestIndexOpeningsAtTheMaximumUnsortedShare(unittest.TestCase):
    def setUp(self) -> None:
        self.allowed_descents = int(MAX_UNSORTED_SHARE * (SAMPLED_ENTRIES - 1))

    def test_a_page_whose_unsorted_share_reaches_the_maximum_opens_an_index(self) -> None:
        self.assertTrue(index_page(entries_with_descents(self.allowed_descents)).opens_an_index())

    def test_a_page_whose_unsorted_share_passes_the_maximum_opens_no_index(self) -> None:
        self.assertFalse(index_page(entries_with_descents(self.allowed_descents + 1)).opens_an_index())


if __name__ == "__main__":
    unittest.main()
