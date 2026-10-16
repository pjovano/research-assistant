from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun
from _drive.work import ListedWorks
from _file.drive import FileDriver, FileScript

PDF = "scan.pdf"
PLACED = "Doe - 2020 - A Work.pdf"
BASENAME = "Doe - 2020 - A Work"
WORK_KEY = 3
COMPLETE_CARD = json.dumps({"missing_for_type": []})
INCOMPLETE_CARD = json.dumps({"missing_for_type": ["publisher"]})
BETTER_BIBTEX_TRACEBACK = ("Traceback (most recent call last):\n"
                           "zotero.BetterBibtexError: Better BibTeX item.search failed: connection refused")


def filed(*rows: dict) -> ScriptRun:
    return ScriptRun(0, json.dumps({"retried_pending": [], "filed": list(rows)}))


def retried(*rows: dict) -> ScriptRun:
    return ScriptRun(0, json.dumps(list(rows)))


def row(status: str, **fields) -> dict:
    return {"file": PDF, "status": status, **fields}


class StubScript(FileScript):
    def __init__(self, results: dict[str, ScriptRun]) -> None:
        super().__init__()
        self.results = results
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self.results.get(args[0], ScriptRun(0, "{}"))


class DriveCase:
    def __init__(self, test: unittest.TestCase, results: dict[str, ScriptRun]) -> None:
        self.works_dir = Path(test.enterContext(tempfile.TemporaryDirectory()))
        self.script = StubScript(results)
        self._driver = FileDriver(self.script, self.works_dir)

    def card(self) -> dict:
        return self._driver.card(PDF)

    def file(self) -> dict:
        return self._driver.file(PDF)

    def file_key(self, key: int) -> dict:
        return self._driver.file(str(key))

    def commands(self) -> list[tuple[str, ...]]:
        return self.script.calls


def card_case(test: unittest.TestCase, bib: ScriptRun, name: ScriptRun | None = None) -> DriveCase:
    return DriveCase(test, {"bib": bib, "name": name or ScriptRun(0, f"{PLACED}\n")})


class TestDraftCardCheck(unittest.TestCase):
    def test_a_complete_card_is_ready_with_its_main_title(self) -> None:
        outcome = card_case(self, ScriptRun(0, COMPLETE_CARD)).card()
        self.assertEqual(("card-ok", "A Work"), (outcome["state"], outcome["title"]))

    def test_a_checked_card_marks_stage_0_done_for_a_later_batch(self) -> None:
        case = card_case(self, ScriptRun(0, COMPLETE_CARD))
        case.card()
        state = json.loads((case.works_dir / Path(PDF).stem / "state.json").read_text())
        self.assertEqual((True, PDF), (state["routed"], state["inbox_pdf"]))

    def test_a_card_missing_a_field_asks_for_a_second_dispatch(self) -> None:
        outcome = card_case(self, ScriptRun(0, INCOMPLETE_CARD)).card()
        self.assertEqual(("redo-card", ["publisher"]), (outcome["state"], outcome["missing"]))

    def test_a_card_still_missing_a_field_after_the_second_dispatch_is_set_aside(self) -> None:
        case = card_case(self, ScriptRun(0, INCOMPLETE_CARD))
        case.card()
        self.assertEqual("aside", case.card()["state"])

    def test_a_name_that_cannot_be_formed_sets_the_pdf_aside(self) -> None:
        name = ScriptRun(1, json.dumps({"error": "no creator surname"}))
        outcome = card_case(self, ScriptRun(0, COMPLETE_CARD), name).card()
        self.assertEqual(("aside", True), (outcome["state"], "no creator surname" in outcome["question"]))

    def test_a_better_bibtex_traceback_halts_the_batch(self) -> None:
        outcome = card_case(self, ScriptRun(1, "", BETTER_BIBTEX_TRACEBACK)).card()
        self.assertEqual("halt", outcome["state"])


class TestFiling(unittest.TestCase):
    def test_a_pdf_filed_under_a_key_lists_the_key_under_its_basename(self) -> None:
        case = DriveCase(self, {"file": filed(row("filed", file=PLACED))})
        ListedWorks(case.works_dir).list(WORK_KEY, PDF)
        case.file_key(WORK_KEY)
        self.assertEqual(PLACED, ListedWorks(case.works_dir).pdf(WORK_KEY))

    def test_the_named_pdf_is_filed_alone(self) -> None:
        case = DriveCase(self, {"file": filed(row("filed", file=PLACED))})
        case.file()
        self.assertEqual([("file", PDF, "--only")], case.commands())

    def test_a_placed_pdf_is_filed_under_its_basename(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("filed", file=PLACED))}).file()
        self.assertEqual(("filed", BASENAME, PDF), (outcome["state"], outcome["basename"], outcome["pdf"]))

    def test_an_unplaced_pdf_is_retried_alone(self) -> None:
        case = DriveCase(self, {"file": filed(row("filed-unverified")),
                                "retry": retried(row("verified-on-retry", file=PLACED))})
        outcome = case.file()
        self.assertEqual(("filed", ("retry", "--only", PDF)), (outcome["state"], case.commands()[-1]))

    def test_the_stall_signature_halts_the_batch(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("filed-unverified")),
                                   "retry": retried(row("still-unverified"))}).file()
        self.assertEqual(("halt", True), (outcome["state"], "stall signature" in outcome["question"]))

    def test_a_pdf_placed_under_another_name_is_set_aside(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("filed-unverified")),
                                   "retry": retried(row("still-unverified", placed_elsewhere=PLACED))}).file()
        self.assertEqual("aside", outcome["state"])

    def test_zotero_offline_halts_the_batch(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("zotero-offline"))}).file()
        self.assertEqual("halt", outcome["state"])

    def test_zotero_still_offline_on_retry_halts_the_batch(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("filed-unverified")),
                                   "retry": ScriptRun(0, json.dumps({"status": "zotero-still-offline"}))}).file()
        self.assertEqual("halt", outcome["state"])

    def test_a_connection_lost_twice_halts_the_batch(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("connection-lost")),
                                   "retry": retried(row("retry-failed"))}).file()
        self.assertEqual(("halt", True), (outcome["state"], "dropped twice" in outcome["question"]))

    def test_a_connection_lost_once_is_filed_by_the_retry(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("connection-lost")),
                                   "retry": retried(row("retried-ok", file=PLACED))}).file()
        self.assertEqual("filed", outcome["state"])

    def test_a_duplicate_sets_the_pdf_aside_with_the_row(self) -> None:
        outcome = DriveCase(self, {"file": filed(row("duplicate", held_as=PLACED))}).file()
        self.assertEqual(("aside", True), (outcome["state"], PLACED in outcome["question"]))

    def test_a_better_bibtex_traceback_halts_the_batch(self) -> None:
        outcome = DriveCase(self, {"file": ScriptRun(1, "", BETTER_BIBTEX_TRACEBACK)}).file()
        self.assertEqual("halt", outcome["state"])

    def test_another_failure_without_a_report_sets_the_pdf_aside(self) -> None:
        outcome = DriveCase(self, {"file": ScriptRun(1, "", "PDF not in the inbox")}).file()
        self.assertEqual("aside", outcome["state"])


if __name__ == "__main__":
    unittest.main()
