from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.backfillrunner import ScriptRun
from _extract.console import EXIT_DOUBTFUL
from test_extract_backfill_driver import CHAPTER_HEADINGS, PAGE_COUNT, BackfillCase, StubScript

DOUBTFUL_PAGE = 12
SCOPE = ["--exclude-nothing"]
FORCED_PAGES = "--force-ocr-pages"


class ExtractionsInTurn(StubScript):
    def __init__(self, *extractions: ScriptRun) -> None:
        super().__init__()
        self._extractions = list(extractions)

    def run(self, *args: str) -> ScriptRun:
        if args[0] != "extract":
            return super().run(*args)
        self.calls.append(args)
        return self._extractions.pop(0)


def doubtful(*pages: int) -> ScriptRun:
    return ScriptRun(EXIT_DOUBTFUL, json.dumps([{"file_page": page, "reason": "garbled"} for page in pages]))


def retrial_case(test: unittest.TestCase, script: StubScript, **state) -> BackfillCase:
    case = BackfillCase(test, script)
    case.put("state.json", {"flags": [], "scope_runs": 0, "scope": SCOPE, **state})
    case.put("probe.json", {"headings": CHAPTER_HEADINGS, "page_count": PAGE_COUNT})
    case.put("doubtful-0.json", {"pages": [{"file_page": DOUBTFUL_PAGE}]})
    case.put("readings-0.json", [{"page": DOUBTFUL_PAGE, "text": "a reading"}])
    return case


def extractions(case: BackfillCase) -> list[tuple[str, ...]]:
    return [call for call in case.script.calls if call[0] == "extract"]


class TestDoubtfulPagesLeftAfterTheReadings(unittest.TestCase):
    def test_their_chapters_are_read_from_pixels_in_a_new_trial(self) -> None:
        case = retrial_case(self, ExtractionsInTurn(doubtful(DOUBTFUL_PAGE), doubtful(DOUBTFUL_PAGE)))
        outcome = case.call("retrial")
        new_trial = extractions(case)[-1]
        self.assertEqual(("doubtful", (FORCED_PAGES, "10-19"), False),
                         (outcome["state"], new_trial[-2:], "--readings" in new_trial))

    def test_the_chapters_read_from_pixels_stay_in_the_works_flags(self) -> None:
        case = retrial_case(self, ExtractionsInTurn(doubtful(DOUBTFUL_PAGE), doubtful(DOUBTFUL_PAGE)))
        case.call("retrial")
        self.assertEqual([FORCED_PAGES, "10-19"], case.read("state.json")["flags"])

    def test_the_readings_of_the_text_layers_pages_are_discarded(self) -> None:
        case = retrial_case(self, ExtractionsInTurn(doubtful(DOUBTFUL_PAGE), doubtful(DOUBTFUL_PAGE)))
        case.call("retrial")
        self.assertFalse((case.work_dir / "readings-0.json").exists())

    def test_doubtful_pages_left_after_the_chapters_were_read_from_pixels_set_the_work_aside(self) -> None:
        case = retrial_case(self, ExtractionsInTurn(doubtful(DOUBTFUL_PAGE)), doubt_read_from_pixels=True)
        self.assertEqual("aside", case.call("retrial")["state"])

    def test_a_doubtful_page_in_a_chapter_already_read_from_pixels_sets_the_work_aside(self) -> None:
        case = retrial_case(self, ExtractionsInTurn(doubtful(DOUBTFUL_PAGE)), flags=[FORCED_PAGES, "10-19"])
        self.assertEqual(("aside", 1), (case.call("retrial")["state"], len(extractions(case))))

    def test_a_work_read_wholly_from_pixels_sets_the_work_aside(self) -> None:
        case = retrial_case(self, ExtractionsInTurn(doubtful(DOUBTFUL_PAGE)), flags=["--force-ocr"])
        self.assertEqual("aside", case.call("retrial")["state"])


if __name__ == "__main__":
    unittest.main()
