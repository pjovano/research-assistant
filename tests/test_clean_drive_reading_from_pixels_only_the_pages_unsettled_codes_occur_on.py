from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun
from test_clean_drive import DriveCase, reported, scanned

UNSETTLED = {("fonts", "scan"): [scanned(0)], ("fonts", "repair"): [reported(status="unresolved-codes-remain")]}
PAGE_COUNT = 10
FLAGGED = [3, 7]


def unsettled_case(test: unittest.TestCase, pages: list[int] | None, page_count: int = PAGE_COUNT) -> DriveCase:
    return DriveCase(test, {**UNSETTLED, ("fonts", "pages"): [reported(pages=pages, page_count=page_count)]})


class TestAPdfWhoseUnsettledCodesOccurOnSomeOfItsPages(unittest.TestCase):
    def test_the_outcome_names_the_listing_of_those_pages(self) -> None:
        outcome = unsettled_case(self, FLAGGED).fonts()
        self.assertEqual(FLAGGED, json.loads(Path(outcome["pixel_pages"]).read_text(encoding="utf-8"))["pages"])

    def test_the_text_layer_is_still_untrusted(self) -> None:
        self.assertTrue(unsettled_case(self, FLAGGED).fonts()["force_ocr"])

    def test_the_note_names_how_many_pages_are_read_from_pixels(self) -> None:
        notes = unsettled_case(self, FLAGGED).fonts()["notes"]
        self.assertIn(f"the {len(FLAGGED)} of {PAGE_COUNT} pages a flagged code occurs on", notes[0])

    def test_nothing_is_repaired(self) -> None:
        case = unsettled_case(self, FLAGGED)
        case.fonts()
        self.assertFalse(case.ran("fonts", "repair", "--apply"))


class TestAPdfStillReadWholeFromPixels(unittest.TestCase):
    def test_codes_on_every_page_read_the_whole_pdf_from_pixels(self) -> None:
        self.assertNotIn("pixel_pages", unsettled_case(self, list(range(1, PAGE_COUNT + 1))).fonts())

    def test_codes_whose_pages_are_unknown_read_the_whole_pdf_from_pixels(self) -> None:
        self.assertNotIn("pixel_pages", unsettled_case(self, None).fonts())

    def test_a_page_listing_naming_no_pages_reads_the_whole_pdf_from_pixels(self) -> None:
        case = DriveCase(self, {**UNSETTLED, ("fonts", "pages"): [reported()]})
        self.assertNotIn("pixel_pages", case.fonts())

    def test_a_failed_page_listing_reads_the_whole_pdf_from_pixels(self) -> None:
        case = DriveCase(self, {**UNSETTLED, ("fonts", "pages"): [ScriptRun(1, "", "the scan failed")]})
        self.assertNotIn("pixel_pages", case.fonts())


if __name__ == "__main__":
    unittest.main()
