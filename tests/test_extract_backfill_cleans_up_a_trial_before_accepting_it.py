from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.numbered import NumberedFiles
from _extract.backfillrunner import ScriptRun
from test_extract_backfill_driver import CHAPTER_HEADINGS, PAGE_COUNT, BackfillCase, StubScript, judged, listing, trial_case

FLAGGED_PAGES = [3, 9]
CORRECTION = {"op": "split", "page": 3, "anchor": "An anchor of six words at least", "family": "entry lists",
              "defect_class": "entries set flush with no hanging indent"}
COUNTS = {"applied": 1, "stale": 0, "unmatched": 0, "refused": 0}


def cleanup_case(test: unittest.TestCase, cleanup: bool, flagged: list[int] = FLAGGED_PAGES) -> BackfillCase:
    script = StubScript({"correction-listing": ScriptRun(0, json.dumps(listing(flagged))),
                         "correct": ScriptRun(0, json.dumps({"written": "trial.md", "counts": COUNTS}))})
    case = trial_case(test, judged(), script, {"cleanup": cleanup})
    case.put("probe.json", {"headings": CHAPTER_HEADINGS, "page_count": PAGE_COUNT})
    (case.work_dir / "trial.md").write_text("# One\n## Inner\n# Two\n# Three\n")
    script.results["extract"] = ScriptRun(0, json.dumps({"written": str(case.work_dir / "trial.md")}))
    return case


def write_corrections(line: dict, corrections: list[dict], skipped: frozenset[int] = frozenset()) -> None:
    for number, part in enumerate(NumberedFiles.expanded(line["dir"], line["parts"])):
        if number not in skipped:
            pages = [page["file_page"] for page in json.loads(Path(part["listing"]).read_text())["pages"]]
            Path(part["verdicts"]).write_text(json.dumps({"pages_read": pages, "corrections": corrections}))


def commands(case: BackfillCase) -> list[str]:
    return [call[0] for call in case.script.calls]


class TestTheCleanupSwitch(unittest.TestCase):
    def test_prep_records_the_cleanup_it_is_given(self) -> None:
        case = BackfillCase(self, StubScript())
        case.invoke("prep", cleanup=True)
        self.assertTrue(case.read("state.json")["cleanup"])

    def test_prep_without_the_cleanup_records_none(self) -> None:
        case = BackfillCase(self, StubScript())
        case.put("state.json", {"cleanup": True})
        case.invoke("prep")
        self.assertFalse(case.read("state.json")["cleanup"])

    def test_without_the_cleanup_the_trial_is_accepted_at_once(self) -> None:
        case = cleanup_case(self, cleanup=False)
        self.assertEqual("accepted", case.call("trial")["state"])
        self.assertNotIn("correction-listing", commands(case))


class TestACleanedUpTrial(unittest.TestCase):
    def test_the_trial_lists_its_doubted_pages_for_the_layout_corrector(self) -> None:
        line = cleanup_case(self, cleanup=True).call("trial")
        self.assertEqual(("cleanup", 1), (line["state"], line["parts"]["count"]))

    def test_a_trial_with_no_doubted_page_is_accepted_at_once(self) -> None:
        self.assertEqual("accepted", cleanup_case(self, cleanup=True, flagged=[]).call("trial")["state"])

    def test_the_corrections_are_applied_before_the_trial_is_accepted(self) -> None:
        case = cleanup_case(self, cleanup=True)
        write_corrections(case.call("trial"), [CORRECTION])
        outcome = case.call("cleanup")
        self.assertEqual("accepted", outcome["state"])
        self.assertLess(commands(case).index("correct"), commands(case).index("accept"))

    def test_the_accepted_notes_count_the_corrections(self) -> None:
        case = cleanup_case(self, cleanup=True)
        write_corrections(case.call("trial"), [CORRECTION])
        self.assertIn("cleanup: 1 corrections applied, 0 refused or unmatched", case.call("cleanup")["notes"])

    def test_a_part_left_unread_goes_to_a_new_layout_corrector_once(self) -> None:
        case = cleanup_case(self, cleanup=True)
        write_corrections(case.call("trial"), [], skipped=frozenset({0}))
        self.assertEqual("recleanup", case.call("cleanup")["state"])
        self.assertEqual("accepted", case.call("cleanup")["state"])


if __name__ == "__main__":
    unittest.main()
