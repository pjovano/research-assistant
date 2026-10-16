from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import references
from apparatus import Apparatus

TEXT_ORIGIN = (72, 72)
TEXT_SIZE = 11
BODY_PAGES = ["Chapter One\n\nSome body text about Kant and mathematics.",
              "Chapter Two\n\nMore body text on the exact sciences."]
BIBLIOGRAPHY_PAGE = ("References\n\n"
                     "Allison, H. (1973). The Kant-Eberhard Controversy. Baltimore: Hopkins.\n"
                     "Friedman, M. (1992). Kant and the Exact Sciences. Cambridge: Harvard.")
BIBLIOGRAPHY_PAGE_NUMBER = len(BODY_PAGES) + 1
TRAILING_PAGE = "Kant, 3\nmathematics, 1\nsciences, 2"
INDEX_HEADINGS = ("General Index", "Author Index 211", "Register", "Index of Names")


class ReferenceZoneOf:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def closing_page(self, index_heading: str) -> int:
        path = self._directory / f"{len(list(self._directory.iterdir()))}.pdf"
        document = pymupdf.open()
        for text in BODY_PAGES + [BIBLIOGRAPHY_PAGE, f"{index_heading}\n\n{TRAILING_PAGE}", TRAILING_PAGE]:
            document.new_page().insert_text(TEXT_ORIGIN, text, fontsize=TEXT_SIZE)
        document.save(path)
        document.close()
        return references.ZoneLocator(path).locate().last_page


class TestAReferenceZoneClosesAtAnIndexOfAnyNameAnIndexHeadingTakes(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.zone = ReferenceZoneOf(Path(directory.name))

    def test_an_index_page_under_any_listed_index_name_closes_the_zone(self) -> None:
        for heading in INDEX_HEADINGS[:3]:
            with self.subTest(heading=heading):
                self.assertEqual(BIBLIOGRAPHY_PAGE_NUMBER, self.zone.closing_page(heading))

    def test_every_name_that_closes_a_zone_is_an_index_heading(self) -> None:
        for heading in INDEX_HEADINGS[:3]:
            with self.subTest(heading=heading):
                self.assertTrue(Apparatus().is_index(heading.rstrip(" 0123456789")))

    def test_a_line_naming_an_index_of_something_does_not_close_the_zone(self) -> None:
        self.assertGreater(self.zone.closing_page(INDEX_HEADINGS[3]), BIBLIOGRAPHY_PAGE_NUMBER)


if __name__ == "__main__":
    unittest.main()
