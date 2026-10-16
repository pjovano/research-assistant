from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.numbered import NumberedFiles
from _extract.backfillparts import SCOPE_PARTS, PartedListing
from _extract.backfillrunner import ScriptRun
from test_extract_backfill_driver import (
    BackfillCase,
    extract_call,
    listing,
    probed,
)

BOUNDARY_PAGES = list(range(1, 25))
CROSSING_SPANS = ({"start": "12: Index", "resume": "13"}, {"start": "13", "resume": "15: Notes"})


def file_pages(part: dict) -> list[int]:
    return [page["file_page"] for page in part["pages"]]


def loaded(path: str) -> dict:
    return json.loads(Path(path).read_text())


def scope_case(test: unittest.TestCase, spans_of_part: tuple[dict, ...]) -> BackfillCase:
    case = BackfillCase(test, probed())
    case.script.results["scope"] = ScriptRun(0, json.dumps(listing(BOUNDARY_PAGES)))
    case.invoke("fonts-checked")
    prepared = case.call("prep")
    parts = NumberedFiles.expanded(prepared["dir"], prepared["parts"])
    for part, span in zip(parts, spans_of_part):
        Path(part["verdicts"]).write_text(json.dumps({"pages_judged": file_pages(loaded(part["listing"])),
                                                      "spans": [span]}))
    return case


class TestAScopeListingSplitIntoParts(unittest.TestCase):
    def parts(self) -> list[dict]:
        return PartedListing(listing(BOUNDARY_PAGES), SCOPE_PARTS).parts()

    def test_a_scope_part_looks_ahead_to_the_first_page_of_the_next(self) -> None:
        self.assertEqual(13, self.parts()[0]["look_ahead"]["file_page"])

    def test_the_last_scope_part_looks_ahead_to_nothing(self) -> None:
        self.assertIsNone(self.parts()[-1]["look_ahead"])

    def test_a_span_crossing_a_part_boundary_settles_in_one_round(self) -> None:
        case = scope_case(self, CROSSING_SPANS)
        case.call("trial")
        self.assertEqual(("--exclude", "12: Index", "13", "--exclude", "13", "15: Notes"), extract_call(case)[3:9])


if __name__ == "__main__":
    unittest.main()
