from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_backfill_driver import BackfillCase, called_commands, probed

FORCE_OCR = "--force-ocr"
FORCE_OCR_PAGES = "--force-ocr-pages"


def converted_from_pixels(case: BackfillCase) -> bool:
    convert = next(call for call in case.script.calls if call[0] == "convert")
    return FORCE_OCR in convert


class TestAWorkWhoseCodesTheFontRepairCannotSettle(unittest.TestCase):
    def test_the_preparation_converts_it_from_pixels(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("prep", fonts_checked=True, pixels_only=True)
        self.assertEqual((True, [FORCE_OCR]), (converted_from_pixels(case), case.read("state.json")["flags"]))

    def test_the_record_alone_lets_the_preparation_convert_without_the_font_repair(self) -> None:
        case = BackfillCase(self, probed())
        outcome = case.invoke("prep", pixels_only=True)
        self.assertEqual(("ready", ["probe", "convert", "scope"]), (outcome["state"], called_commands(case)))

    def test_the_record_survives_a_later_preparation(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("prep", pixels_only=True)
        case.invoke("prep")
        self.assertEqual((True, [FORCE_OCR]), (case.read("state.json")["pixels_only"],
                                               case.read("state.json")["flags"]))

    def test_the_record_of_the_font_repair_reads_it_from_pixels_before_it_is_converted(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("fonts-checked", pixels_only=True)
        self.assertEqual(([], True, True), (called_commands(case), case.read("state.json")["pixels_only"],
                                            case.read("state.json")["fonts_checked"]))

    def test_a_work_with_no_record_converts_from_its_text_layer(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("prep", fonts_checked=True)
        self.assertFalse(converted_from_pixels(case))


class TestAWorkWhoseUnsettledCodesOccurOnSomeOfItsPages(unittest.TestCase):
    def recorded(self, listing: object) -> tuple[BackfillCase, dict]:
        case = BackfillCase(self, probed())
        path = case.work_dir.parent / "pixel-pages.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(listing), encoding="utf-8")
        return case, case.invoke("fonts-checked", pixel_pages=path)

    def test_the_preparation_converts_those_pages_from_pixels(self) -> None:
        case, _ = self.recorded({"pages": [3, 7, 8]})
        case.invoke("prep")
        convert = next(call for call in case.script.calls if call[0] == "convert")
        self.assertEqual((FORCE_OCR_PAGES, "3,7-8"), convert[-2:])

    def test_the_record_keeps_the_pages_for_every_later_conversion(self) -> None:
        case, _ = self.recorded({"pages": [3, 7, 8]})
        case.invoke("prep")
        self.assertEqual([FORCE_OCR_PAGES, "3,7-8"], case.read("state.json")["flags"])

    def test_the_record_counts_as_the_font_repair(self) -> None:
        _, outcome = self.recorded({"pages": [3]})
        self.assertEqual("fonts-checked", outcome["state"])

    def test_a_listing_naming_no_pages_sets_the_work_aside(self) -> None:
        _, outcome = self.recorded({"pages": []})
        self.assertEqual("aside", outcome["state"])


if __name__ == "__main__":
    unittest.main()
