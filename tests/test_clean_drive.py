from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.numbered import NumberedFiles
from _clean.drive import CleanDriver
from _clean.drivefonts import CleanScript
from _clean.readeranswers import MAX_UNRESOLVED_CODES
from _drive.script import ScriptRun, SkillScript

PDF = "scan.pdf"
APPLY = "--apply"
CODE = {"font": "CMSY10", "code": "7E", "glyph_name": None, "unicode": "U+007E"}
VISION_UNRESPONSIVE = "Apple Vision returned no reading of a line within 30 seconds"
NOT_IN_CACHE = "huggingface_hub.errors.LocalEntryNotFoundError: cannot find the requested files in the disk cache"


def scanned(unresolved: int, unread_sheets: int = 0) -> ScriptRun:
    return ScriptRun(0, json.dumps({"codes_unresolved": unresolved, "pixels": {"unread_sheets": unread_sheets}}))


def reported(**payload) -> ScriptRun:
    return ScriptRun(0, json.dumps(payload))


def read_from_pixels(outcome: dict) -> tuple[str, bool]:
    return outcome["state"], outcome.get("force_ocr", False)


def learned(**groups) -> ScriptRun:
    return reported(**{"learn": [], "conflicts": [], "unresolved": [], "set_aside": [], "needs_no_repair": [],
                       **groups})


class StubScript(CleanScript):
    def __init__(self, results: dict[tuple, list[ScriptRun]]) -> None:
        super().__init__()
        self.results = {key: list(runs) for key, runs in results.items()}
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        runs = self.results.get(self.key(args), [ScriptRun(0, "{}")])
        return runs.pop(0) if len(runs) > 1 else runs[0]

    @staticmethod
    def key(args: tuple[str, ...]) -> tuple:
        command = args[:2] if args[0] == "fonts" else args[:1]
        return (*command, APPLY) if APPLY in args else command


class StubVolumes(SkillScript):
    def __init__(self) -> None:
        super().__init__(Path("volumes.py"))

    def run(self, *args: str) -> ScriptRun:
        return reported(chapters=[{"title": "One", "file_pages": [3, 20]}])


class DriveCase:
    def __init__(self, test: unittest.TestCase, results: dict[tuple, list[ScriptRun]]) -> None:
        self.works_dir = Path(test.enterContext(tempfile.TemporaryDirectory()))
        self.script = StubScript(results)
        self._driver = CleanDriver(self.script, StubVolumes(), self.works_dir)

    @property
    def work_dir(self) -> Path:
        return self.works_dir / Path(PDF).stem

    def fonts(self) -> dict:
        return self._driver.fonts(PDF)

    def learn(self) -> dict:
        return self._driver.learn(PDF)

    def route(self, kind: str) -> dict:
        return self._driver.route(PDF, kind)

    def put(self, name: str, payload: object) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        (self.work_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    def ran(self, *command: str) -> bool:
        return any(StubScript.key(call) == command for call in self.script.calls)


class TestFontScan(unittest.TestCase):
    def test_no_unresolved_code_is_repaired_without_a_glyph_read(self) -> None:
        case = DriveCase(self, {("fonts", "scan"): [scanned(0)], ("fonts", "repair"): [reported(status="would-repair")],
                                ("fonts", "repair", APPLY): [reported(status="repaired")]})
        self.assertEqual(("bookmark", True), (case.fonts()["state"], case.ran("fonts", "repair", APPLY)))

    def test_no_unresolved_code_and_a_repair_left_unresolved_reads_the_pdf_from_pixels(self) -> None:
        case = DriveCase(self, {("fonts", "scan"): [scanned(0)],
                                ("fonts", "repair"): [reported(status="unresolved-codes-remain")]})
        self.assertEqual(("bookmark", True), read_from_pixels(case.fonts()))

    def test_unresolved_codes_are_listed_for_the_glyph_reader(self) -> None:
        case = DriveCase(self, {("fonts", "scan"): [scanned(1)],
                                ("fonts", "identify"): [reported(pdf=PDF, renders="r", codes=[CODE])]})
        outcome = case.fonts()
        listing = json.loads(Path(NumberedFiles.expanded(outcome["dir"], outcome["groups"])[0]["codes"]).read_text(encoding="utf-8"))
        self.assertEqual(("glyphs", [CODE], True), (outcome["state"], listing["codes"],
                                                     NumberedFiles.expanded(outcome["dir"], outcome["groups"])[0]["answers"].endswith("answers-1.json")))

    def test_more_unresolved_codes_than_a_glyph_read_settles_read_the_pdf_from_pixels_unrepaired(self) -> None:
        case = DriveCase(self, {("fonts", "scan"): [scanned(MAX_UNRESOLVED_CODES + 1)]})
        outcome = case.fonts()
        self.assertEqual(("bookmark", True, False, False),
                         (*read_from_pixels(outcome), case.ran("fonts", "identify"), case.ran("fonts", "repair")))

    def test_an_unread_sheet_is_scanned_once_more(self) -> None:
        case = DriveCase(self, {("fonts", "scan"): [scanned(0, unread_sheets=1), scanned(0)],
                                ("fonts", "repair"): [reported(status="nothing-to-repair")]})
        self.assertEqual(("bookmark", 2), (case.fonts()["state"],
                                           sum(StubScript.key(call) == ("fonts", "scan") for call in case.script.calls)))

    def test_an_unread_sheet_on_the_second_scan_sets_the_pdf_aside(self) -> None:
        outcome = DriveCase(self, {("fonts", "scan"): [scanned(0, unread_sheets=1)]}).fonts()
        self.assertEqual("aside", outcome["state"])

    def test_apple_vision_unresponsive_twice_sets_the_pdf_aside(self) -> None:
        outcome = DriveCase(self, {("fonts", "scan"): [ScriptRun(1, "", VISION_UNRESPONSIVE)]}).fonts()
        self.assertEqual("aside", outcome["state"])

    def test_vision_unavailable_halts_the_batch(self) -> None:
        unavailable = ScriptRun(1, json.dumps({"status": "vision-unavailable", "error": "ocrmac runs only on macOS; "
                                                                                       "Apple Vision"}))
        self.assertEqual("halt", DriveCase(self, {("fonts", "scan"): [unavailable]}).fonts()["state"])

    def test_a_model_missing_from_the_cache_halts_the_batch(self) -> None:
        missing = ScriptRun(1, "", NOT_IN_CACHE)
        self.assertEqual("halt", DriveCase(self, {("fonts", "scan"): [missing]}).fonts()["state"])

    def test_an_unparsable_identity_table_halts_the_batch(self) -> None:
        unparsable = ScriptRun(1, "", "The identity table glyph-identities.json is not valid JSON: line 3")
        self.assertEqual("halt", DriveCase(self, {("fonts", "scan"): [unparsable]}).fonts()["state"])


def learn_case(test: unittest.TestCase, plan: ScriptRun, repair: str | ScriptRun = "would-repair") -> DriveCase:
    dry_run = repair if isinstance(repair, ScriptRun) else reported(status=repair)
    case = DriveCase(test, {("fonts", "learn-reader"): [plan], ("fonts", "learn-reader", APPLY): [learned()],
                            ("fonts", "repair"): [dry_run],
                            ("fonts", "repair", APPLY): [reported(status="repaired")]})
    case.put("identify.json", {"pdf": PDF, "codes": [CODE]})
    case.put("answers-0.json", [{"font": "CMSY10", "glyph": "7E", "unicode": "∼", "evidence": "a tilde"}])
    return case


class TestLearnAndRepair(unittest.TestCase):
    def test_the_answers_are_learned_and_the_pdf_repaired(self) -> None:
        case = learn_case(self, learned())
        outcome = case.learn()
        self.assertEqual(("bookmark", True, True), (outcome["state"], case.ran("fonts", "learn-reader", APPLY),
                                                    case.ran("fonts", "repair", APPLY)))

    def test_a_conflict_keeps_the_tables_entry_and_goes_to_the_report(self) -> None:
        outcome = learn_case(self, learned(conflicts=[{"key": "CMSY10|#7E"}])).learn()
        self.assertEqual(("bookmark", 1), (outcome["state"], len(outcome["notes"])))

    def test_an_unresolved_glyph_reads_the_pdf_from_pixels_without_learning_or_repairing(self) -> None:
        case = learn_case(self, learned(unresolved=[{"font": "CMSY10", "glyph": "7E"}]))
        self.assertEqual(("bookmark", True, False, False),
                         (*read_from_pixels(case.learn()), case.ran("fonts", "learn-reader", APPLY),
                          case.ran("fonts", "repair")))

    def test_an_answer_the_table_cannot_take_reads_the_pdf_from_pixels_learning_nothing(self) -> None:
        case = learn_case(self, learned(set_aside=[{"font": "Baskerville", "reason": "outside a TeX family"}]))
        self.assertEqual(("bookmark", True, False),
                         (*read_from_pixels(case.learn()), case.ran("fonts", "learn-reader", APPLY)))

    def test_codes_left_unresolved_by_the_repair_read_the_pdf_from_pixels(self) -> None:
        outcome = learn_case(self, learned(), repair="unresolved-codes-remain").learn()
        self.assertEqual(("bookmark", True), read_from_pixels(outcome))

    def test_a_repair_failing_its_verification_reads_the_pdf_from_pixels(self) -> None:
        case = learn_case(self, learned())
        case.script.results[("fonts", "repair", APPLY)] = [reported(status="verification-failed", reason="kept")]
        self.assertEqual(("bookmark", True), read_from_pixels(case.learn()))

    def test_a_repair_reporting_an_unknown_status_still_sets_the_pdf_aside(self) -> None:
        self.assertEqual("aside", learn_case(self, learned(), repair="unforeseen").learn()["state"])

    def test_nothing_to_repair_writes_nothing(self) -> None:
        case = learn_case(self, learned(), repair="nothing-to-repair")
        self.assertEqual(("bookmark", False), (case.learn()["state"], case.ran("fonts", "repair", APPLY)))

    def test_a_listing_with_no_answers_file_asks_for_the_glyph_reader_again(self) -> None:
        case = learn_case(self, learned())
        (case.work_dir / "answers-0.json").unlink()
        self.assertEqual("unwritten", case.learn()["state"])

    def test_a_group_listing_with_no_answers_file_beside_an_answered_one_asks_for_the_glyph_reader_again(self) -> None:
        case = learn_case(self, learned())
        case.put("identify-0.json", {"pdf": PDF, "codes": [CODE]})
        case.put("identify-1.json", {"pdf": PDF, "codes": [CODE]})
        self.assertEqual(("unwritten", False), (case.learn()["state"], case.ran("fonts", "learn-reader")))

    def test_no_listing_needs_no_answers(self) -> None:
        case = DriveCase(self, {("fonts", "repair"): [reported(status="nothing-to-repair")]})
        self.assertEqual("bookmark", case.learn()["state"])


RE_ENCODED_CODE = {"font": "TimesNewRomanPSMT", "glyph": "3d", "unicode": "="}
LEFT_AS_IS = learned(needs_no_repair=[RE_ENCODED_CODE])


def repair_leaving(*codes: str, status: str) -> ScriptRun:
    unresolved = [{"font": "TimesNewRomanPSMT", "code": code, "glyph_name": None} for code in codes]
    return reported(status=status, partial=status == "would-repair", unresolved=unresolved)


class TestCodesThatNeedNoRepair(unittest.TestCase):
    def test_a_pdf_whose_only_unresolved_codes_need_no_repair_is_left_unrepaired(self) -> None:
        case = learn_case(self, LEFT_AS_IS, repair=repair_leaving("3D", status="unresolved-codes-remain"))
        self.assertEqual(("bookmark", False), (case.learn()["state"], case.ran("fonts", "repair", APPLY)))

    def test_codes_that_need_no_repair_beside_patches_are_repaired_partially(self) -> None:
        case = learn_case(self, LEFT_AS_IS, repair=repair_leaving("3D", status="would-repair"))
        outcome = case.learn()
        self.assertEqual(("bookmark", True), (outcome["state"], ("fonts", "repair", PDF, APPLY, "--partial")
                                              in case.script.calls))

    def test_an_unresolved_code_beside_codes_that_need_no_repair_reads_the_pdf_from_pixels(self) -> None:
        case = learn_case(self, LEFT_AS_IS, repair=repair_leaving("3D", "2B", status="unresolved-codes-remain"))
        self.assertEqual(("bookmark", True), read_from_pixels(case.learn()))

    def test_a_repair_with_no_code_left_as_is_is_never_partial(self) -> None:
        case = learn_case(self, learned(), repair=repair_leaving("3D", status="would-repair"))
        case.learn()
        self.assertNotIn("--partial", [argument for call in case.script.calls for argument in call])


class TestRoute(unittest.TestCase):
    def test_an_article_or_a_book_goes_to_filing(self) -> None:
        self.assertEqual("file", DriveCase(self, {}).route("book")["state"])

    def test_a_routed_pdf_records_its_kind_for_a_later_batch(self) -> None:
        case = DriveCase(self, {})
        case.route("article")
        self.assertEqual("article", json.loads((case.work_dir / "state.json").read_text())["routed"])

    def test_a_volume_is_moved_and_set_aside_with_its_chapters(self) -> None:
        case = DriveCase(self, {("volume",): [reported(move=PDF)], ("volume", APPLY): [reported(moved=PDF)]})
        outcome = case.route("volume")
        self.assertEqual(("aside", True, True), (outcome["state"], "One" in outcome["question"],
                                                 case.ran("volume", APPLY)))

    def test_a_volume_already_among_the_volumes_is_set_aside_unmoved(self) -> None:
        case = DriveCase(self, {("volume",): [ScriptRun(1, "", f"Already among the volumes: {PDF}")]})
        outcome = case.route("volume")
        self.assertEqual(("aside", False), (outcome["state"], case.ran("volume", APPLY)))


if __name__ == "__main__":
    unittest.main()
