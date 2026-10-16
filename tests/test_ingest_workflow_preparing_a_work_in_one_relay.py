from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const steps = []
let lines = []
async function extractDrive(step, key, extra) { steps.push([step, extra || null]); return lines.shift() }
async function repairFonts(key) { steps.push(['font repair', null]); return lines.shift() }
"""
READY = {"state": "ready", "parts": []}
RECORDED = {"state": "fonts-checked"}


class TestPreparingAWorkInOneRelay(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations("FONTS_CHECKED_FLAG", "PIXELS_ONLY_FLAG",
                                                                       "PIXEL_PAGES_FLAG", "FONTS_CHECKED_STATE",
                                                                       "unsettledReading", "checkedFonts", "prepared")

    def steps(self, cleaned: bool, *lines: dict, pixels_only: bool = False) -> list:
        program = (f"{self.source}\nlines = {json.dumps(list(lines))}\n"
                   f"prepared('7', [], {json.dumps(cleaned)}, {json.dumps(pixels_only)})"
                   f".then(() => console.log(JSON.stringify(steps)))")
        return json.loads(self.runtime.printed(program))

    def test_a_cleaned_work_is_prepared_in_one_step(self) -> None:
        self.assertEqual([["drive-prep", "--fonts-checked"]], self.steps(True, READY))

    def test_a_backfill_work_asking_for_fonts_records_its_repair_before_it_waits_to_be_prepared(self) -> None:
        steps = self.steps(False, {"state": "fonts"}, {"state": "bookmark"}, RECORDED, READY)
        self.assertEqual([["drive-prep", None], ["font repair", None], ["drive-fonts-checked", None],
                          ["drive-prep", None]], steps)

    def test_a_cleaned_work_whose_codes_stay_unsettled_is_prepared_to_read_pixels(self) -> None:
        self.assertEqual([["drive-prep", "--fonts-checked --pixels-only"]], self.steps(True, READY, pixels_only=True))

    def test_a_backfill_work_whose_codes_stay_unsettled_is_recorded_to_read_pixels(self) -> None:
        steps = self.steps(False, {"state": "fonts"}, {"state": "bookmark", "force_ocr": True}, RECORDED, READY)
        self.assertEqual(["drive-fonts-checked", "--pixels-only"], steps[-2])

    def test_a_backfill_work_whose_unsettled_codes_occur_on_some_pages_is_recorded_to_read_those_from_pixels(self):
        unsettled = {"state": "bookmark", "force_ocr": True, "pixel_pages": "/by-key/7/pixel-pages.json"}
        steps = self.steps(False, {"state": "fonts"}, unsettled, RECORDED, READY)
        self.assertEqual(["drive-fonts-checked", "--pixel-pages /by-key/7/pixel-pages.json"], steps[-2])

    def test_a_backfill_work_whose_repair_record_fails_is_not_prepared(self) -> None:
        steps = self.steps(False, {"state": "fonts"}, {"state": "bookmark"}, {"state": "aside"})
        self.assertEqual(["drive-fonts-checked", None], steps[-1])

    def test_a_backfill_work_already_checked_is_prepared_in_one_step(self) -> None:
        self.assertEqual([["drive-prep", None]], self.steps(False, READY))


if __name__ == "__main__":
    unittest.main()
