from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.backfillrunner import ScriptRun
from test_extract_backfill_driver import PAGE_COUNT, BackfillCase, called_commands, probed

FORCE_OCR = "--force-ocr"
FORCE_OCR_PAGES = "--force-ocr-pages"
SAMPLE_READING_THE_LAYER = {"reads": "layer", "pixel_pages": None, "flags": []}
SAMPLE_READING_ONE_CHAPTER_FROM_PIXELS = {"reads": "layer", "pixel_pages": "10-19",
                                          "flags": [FORCE_OCR_PAGES, "10-19"]}
SAMPLE_READING_PIXELS = {"reads": "pixels", "pixel_pages": None, "flags": [FORCE_OCR]}
THIN_LAYER = PAGE_COUNT // 2


def scan_case(test: unittest.TestCase, sample: dict, pages_with_text: int = PAGE_COUNT) -> BackfillCase:
    script = probed(scanned=True, pages_with_text=pages_with_text)
    script.results["layer-sample"] = ScriptRun(0, json.dumps(sample))
    case = BackfillCase(test, script)
    case.invoke("fonts-checked")
    return case


def conversion_flags(case: BackfillCase) -> list[str]:
    convert = next(call for call in case.script.calls if call[0] == "convert")
    return [arg for arg in convert[1:] if not arg.endswith(".pdf")]


class TestPreparingAScanWhoseLayerCoversItsPages(unittest.TestCase):
    def test_the_layer_is_sampled_before_the_scan_is_converted(self) -> None:
        case = scan_case(self, SAMPLE_READING_THE_LAYER)
        case.call("prep")
        self.assertEqual(["probe", "layer-sample", "convert", "scope"], called_commands(case))

    def test_a_sample_reading_the_layer_converts_the_scan_from_its_text_layer(self) -> None:
        case = scan_case(self, SAMPLE_READING_THE_LAYER)
        case.call("prep")
        self.assertEqual(([], []), (conversion_flags(case), case.read("state.json")["flags"]))

    def test_the_chapters_a_sample_reads_from_pixels_are_converted_from_pixels(self) -> None:
        case = scan_case(self, SAMPLE_READING_ONE_CHAPTER_FROM_PIXELS)
        case.call("prep")
        self.assertEqual([FORCE_OCR_PAGES, "10-19"], conversion_flags(case))

    def test_a_sample_reading_pixels_converts_every_page_from_pixels(self) -> None:
        case = scan_case(self, SAMPLE_READING_PIXELS)
        case.call("prep")
        self.assertEqual([FORCE_OCR], conversion_flags(case))

    def test_the_sample_is_kept_for_every_later_preparation(self) -> None:
        case = scan_case(self, SAMPLE_READING_ONE_CHAPTER_FROM_PIXELS)
        case.call("prep")
        case.call("prep")
        self.assertEqual((1, [FORCE_OCR_PAGES, "10-19"]), (called_commands(case).count("layer-sample"),
                                                           case.read("state.json")["flags"]))

    def test_the_sample_is_kept_beside_the_works_state(self) -> None:
        case = scan_case(self, SAMPLE_READING_ONE_CHAPTER_FROM_PIXELS)
        case.call("prep")
        self.assertEqual(SAMPLE_READING_ONE_CHAPTER_FROM_PIXELS, case.read("layer-sample.json"))

    def test_a_sample_naming_no_reading_sets_the_scan_aside(self) -> None:
        case = scan_case(self, {"flags": []})
        self.assertEqual("aside", case.call("prep")["state"])


class TestPreparingAScanWhoseLayerIsThin(unittest.TestCase):
    def test_it_is_converted_from_pixels_without_a_sample(self) -> None:
        case = scan_case(self, SAMPLE_READING_THE_LAYER, pages_with_text=THIN_LAYER)
        case.call("prep")
        self.assertEqual((["probe", "convert", "scope"], [FORCE_OCR]), (called_commands(case),
                                                                       conversion_flags(case)))


class TestPreparingAScanTheFontRepairReadsFromPixels(unittest.TestCase):
    def test_it_is_converted_from_pixels_without_a_sample(self) -> None:
        case = scan_case(self, SAMPLE_READING_THE_LAYER)
        case.invoke("prep", pixels_only=True)
        self.assertEqual(("layer-sample" in called_commands(case), [FORCE_OCR]), (False, conversion_flags(case)))


if __name__ == "__main__":
    unittest.main()
