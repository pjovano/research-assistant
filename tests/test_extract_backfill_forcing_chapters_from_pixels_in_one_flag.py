from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.pixelchapters import PixelChapters
from test_extract_backfill_driver import CHAPTER_HEADINGS, PAGE_COUNT

FORCED_PAGES = "--force-ocr-pages"


def chapters() -> PixelChapters:
    return PixelChapters(CHAPTER_HEADINGS, PAGE_COUNT)


class TestForcedChaptersInOneFlag(unittest.TestCase):
    def test_pages_in_two_chapters_force_both_chapters_in_one_flag(self) -> None:
        self.assertEqual([FORCED_PAGES, "3-9,20-30"], chapters().flags_covering([], [4, 25]))

    def test_a_later_chapter_joins_the_chapters_forced_before(self) -> None:
        self.assertEqual([FORCED_PAGES, "3-19"], chapters().flags_covering([FORCED_PAGES, "3-9"], [12]))


class TestWideningTheChaptersReadFromPixels(unittest.TestCase):
    def test_a_page_in_a_chapter_not_yet_forced_widens(self) -> None:
        self.assertTrue(chapters().widens([FORCED_PAGES, "3-9"], [12]))

    def test_a_page_in_a_chapter_already_forced_does_not_widen(self) -> None:
        self.assertFalse(chapters().widens([FORCED_PAGES, "10-19"], [12]))

    def test_a_work_read_wholly_from_pixels_does_not_widen(self) -> None:
        self.assertFalse(chapters().widens(["--force-ocr"], [12]))

    def test_a_work_with_no_chapters_forces_every_page(self) -> None:
        self.assertEqual([FORCED_PAGES, f"1-{PAGE_COUNT}"], PixelChapters([], PAGE_COUNT).flags_covering([], [5]))


if __name__ == "__main__":
    unittest.main()
