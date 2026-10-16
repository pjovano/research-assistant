from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.numbered import NumberedFiles
from _extract.backfill import BackfillCommands
from _extract.backfillrunner import ExtractScript, ScriptRun
from _extract.backfillstep import DetachedStep, ProcessProbe, StepHost, StepLauncher, SystemClock
from _extract.backfillverify import TrialVerification
from _drive.work import ListedWorks
from _extract.backfillwork import BackfillQueue

PDF = "Author - 2000 - Work.pdf"
WORK_KEY = 1
LISTED_PAGES = [3, 4, 5, 9]
CHAPTER_HEADINGS = [{"title": "One", "file_page": 3, "level": 1}, {"title": "Inner", "file_page": 5, "level": 2},
                    {"title": "Two", "file_page": 10, "level": 1}, {"title": "Three", "file_page": 20, "level": 1}]
PAGE_COUNT = 30
PREP_RECORDS_OFF = {"fonts_checked": False, "pixels_only": False, "pixel_pages": None, "one_chapter": False,
                    "cleanup": False}


class StubScript(ExtractScript):
    def __init__(self, results: dict[str, ScriptRun] | None = None) -> None:
        super().__init__()
        self.results = results or {}
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        key = " ".join(arg for arg in args if arg != PDF)
        return self.results.get(key, self.results.get(args[0], ScriptRun(0, "{}")))


ENGINE_STEPS = ("prep", "trial", "retrial")
STEP_PID = 4242
SHORT_WAIT_SECONDS = 12


class RecordingLauncher(StepLauncher):
    def __init__(self) -> None:
        super().__init__()
        self.launches: list[tuple[str, int]] = []
        self.commands: BackfillCommands | None = None

    def launch(self, step: str, index: int) -> int:
        self.launches.append((step, index))
        return STEP_PID


class InlineLauncher(RecordingLauncher):
    def launch(self, step: str, index: int) -> int:
        self.commands.run(argparse.Namespace(command="drive-run", step=step, index=index))
        return super().launch(step, index)


class StubProbe(ProcessProbe):
    def __init__(self, alive: bool = False) -> None:
        self.alive = alive

    def is_alive(self, pid: int) -> bool:
        return self.alive


class StubClock(SystemClock):
    def __init__(self) -> None:
        self.elapsed = 0.0

    def now(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds


class BackfillCase:
    def __init__(self, test: unittest.TestCase, script: StubScript, launcher: RecordingLauncher | None = None) -> None:
        directory = Path(test.enterContext(tempfile.TemporaryDirectory())) / "backfill"
        directory.mkdir()
        (directory / "queue.txt").write_text(PDF + "\n")
        self.work_dir = directory / "works" / Path(PDF).stem
        self.work_dir.mkdir(parents=True)
        self.script = script
        self.launcher = launcher or InlineLauncher()
        self.probe = StubProbe()
        self.clock = StubClock()
        self.host = StepHost(self.launcher, self.probe, self.clock)
        self.ingest_dir = directory.parent / "ingest"
        ListedWorks(self.ingest_dir).list(WORK_KEY, PDF)
        self._commands = BackfillCommands(directory, script, self.host)
        self.launcher.commands = self._commands

    def put(self, name: str, data) -> None:
        (self.work_dir / name).write_text(json.dumps(data))

    def read(self, name: str):
        return json.loads((self.work_dir / name).read_text())

    def call(self, step: str, review: int = 1) -> dict:
        return self.invoke(step, review)

    def invoke(self, step: str, review: int = 1, **recorded: bool) -> dict:
        args = argparse.Namespace(command=f"drive-{step}", index=WORK_KEY, review=review,
                                  **{**PREP_RECORDS_OFF, **recorded})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            getattr(self._commands, step.replace("-", "_"))(args)
        return json.loads(output.getvalue())


def trial_case(test: unittest.TestCase, verdicts: dict, script: StubScript | None = None,
               state: dict | None = None) -> BackfillCase:
    case = BackfillCase(test, script or StubScript())
    state = {"flags": [], "scope_runs": 0, **(state or {})}
    case.put("state.json", state)
    case.put("scope.json", listing(LISTED_PAGES))
    case.put("probe.json", {"headings": [], "page_count": PAGE_COUNT})
    case.put(f"scope-verdicts-{state['scope_runs']}-1.json", verdicts)
    return case


def listing(pages: list[int]) -> dict:
    return {"pages": [{"file_page": page} for page in pages]}


def relisting_case(test: unittest.TestCase, verdicts: dict, added: list[int], state: dict | None = None) -> BackfillCase:
    relisted = ScriptRun(0, json.dumps(listing(sorted(LISTED_PAGES + added))))
    return trial_case(test, verdicts, StubScript({"scope": relisted}), state)


def scope_options(case: BackfillCase) -> tuple[str, ...]:
    return next(call for call in case.script.calls if call[0] == "scope")[2:]


def listed_pages(case: BackfillCase) -> list[int]:
    return [page["file_page"] for page in case.read("scope.json")["pages"]]


def last_page_case(test: unittest.TestCase, span: dict) -> BackfillCase:
    pages = [*LISTED_PAGES, PAGE_COUNT]
    case = trial_case(test, {"pages_judged": pages, "spans": [span]})
    case.put("scope.json", listing(pages))
    return case


def judged(*spans: dict) -> dict:
    return {"pages_judged": LISTED_PAGES, "spans": list(spans)}


def extract_call(case: BackfillCase) -> tuple[str, ...]:
    return next(call for call in case.script.calls if call[0] == "extract")


class TestScopeSettlement(unittest.TestCase):
    def test_each_span_becomes_an_exclude_argument(self) -> None:
        case = trial_case(self, judged({"start": "3", "resume": "5: Chapter"}))
        case.call("trial")
        self.assertEqual(("--exclude", "3", "5: Chapter"), extract_call(case)[3:6])

    def test_no_span_excludes_nothing(self) -> None:
        case = trial_case(self, judged())
        case.call("trial")
        self.assertIn("--exclude-nothing", extract_call(case))


    def test_a_span_resuming_at_the_end_passes_the_end_point_to_the_extraction(self) -> None:
        case = last_page_case(self, {"start": f"{PAGE_COUNT}: Received", "resume": "end"})
        case.call("trial")
        self.assertEqual(("--exclude", f"{PAGE_COUNT}: Received", "end"), extract_call(case)[3:6])

    def test_verdicts_omitting_listed_pages_send_only_those_pages_to_a_scoper(self) -> None:
        case = trial_case(self, {"pages_judged": [3], "spans": []})
        outcome = case.call("trial")
        repair = json.loads(Path(NumberedFiles.expanded(outcome["dir"], outcome["parts"])[0]["listing"]).read_text())
        self.assertEqual(("rejudge", [4, 5, 9]), (outcome["state"], [page["file_page"] for page in repair["pages"]]))

    def test_a_rejudged_page_counts_toward_the_same_scope_run(self) -> None:
        case = trial_case(self, {"pages_judged": [3], "spans": []})
        outcome = case.call("trial")
        self.assertEqual((0, True), (case.read("state.json")["scope_runs"],
                                     NumberedFiles.expanded(outcome["dir"], outcome["parts"])[0]["verdicts"].endswith("scope-verdicts-0-repair-1-1.json")))

    def test_the_rejudged_verdicts_merge_with_the_first(self) -> None:
        case = trial_case(self, {"pages_judged": [3], "spans": [{"start": "3", "resume": "4"}]})
        outcome = case.call("trial")
        Path(NumberedFiles.expanded(outcome["dir"], outcome["parts"])[0]["verdicts"]).write_text(json.dumps(judged({"start": "9", "resume": "10"})))
        case.call("trial")
        self.assertEqual(("--exclude", "3", "4", "--exclude", "9", "10"), extract_call(case)[3:9])

    def test_verdicts_omitting_pages_after_the_rejudging_ask_for_a_new_scope(self) -> None:
        case = trial_case(self, {"pages_judged": [3], "spans": []})
        case.call("trial")
        outcome = case.call("trial")
        self.assertEqual(("rescope", True), (outcome["state"],
                                             NumberedFiles.expanded(outcome["dir"], outcome["parts"])[0]["verdicts"].endswith("scope-verdicts-1-1.json")))


SEEN_SPAN = {"start": "3", "resume": "4"}
UNLISTED_SEE_PAGES = [12, 13]
DOUBT_REASON = "the page may carry a translator's note"
DOUBTED_SPAN = {**SEEN_SPAN, "ambiguous": True, "reason": DOUBT_REASON}


class TestPagesTheScoperDidNotSee(unittest.TestCase):
    def test_see_pages_missing_from_the_listing_ask_for_a_new_scope(self) -> None:
        outcome = relisting_case(self, judged({**SEEN_SPAN, "see": UNLISTED_SEE_PAGES}), UNLISTED_SEE_PAGES).call("trial")
        self.assertEqual(("rescope", True), (outcome["state"],
                                             NumberedFiles.expanded(outcome["dir"], outcome["parts"])[0]["verdicts"].endswith("scope-verdicts-1-1.json")))

    def test_see_pages_missing_from_the_listing_are_named_to_the_scope_listing(self) -> None:
        case = relisting_case(self, judged({**SEEN_SPAN, "see": UNLISTED_SEE_PAGES}), UNLISTED_SEE_PAGES)
        case.call("trial")
        self.assertEqual(("--page", "12", "--page", "13"), scope_options(case))

    def test_see_pages_missing_from_the_listing_are_written_into_it(self) -> None:
        case = relisting_case(self, judged({**SEEN_SPAN, "see": UNLISTED_SEE_PAGES}), UNLISTED_SEE_PAGES)
        case.call("trial")
        self.assertEqual([3, 4, 5, 9, 12, 13], listed_pages(case))

    def test_the_new_scope_note_names_the_pages_added(self) -> None:
        case = relisting_case(self, judged({**SEEN_SPAN, "see": UNLISTED_SEE_PAGES}), UNLISTED_SEE_PAGES)
        self.assertIn("file pages 12, 13", case.call("trial")["note"])

    def test_see_pages_the_listing_names_go_on_to_the_extraction(self) -> None:
        case = trial_case(self, judged({**SEEN_SPAN, "see": [9]}))
        case.call("trial")
        self.assertEqual(["extract"], [call[0] for call in case.script.calls if call[0] in ("scope", "extract")])

    def test_a_span_across_unlisted_pages_asks_for_a_new_scope_naming_them(self) -> None:
        outcome = relisting_case(self, judged({"start": "5", "resume": "9"}), [6, 7, 8]).call("trial")
        self.assertEqual(("rescope", True), (outcome["state"], "file pages 6, 7, 8" in outcome["note"]))

    def test_a_span_across_unlisted_pages_adds_them_to_the_listing(self) -> None:
        case = relisting_case(self, judged({"start": "5", "resume": "9"}), [6, 7, 8])
        case.call("trial")
        self.assertEqual([3, 4, 5, 6, 7, 8, 9], listed_pages(case))

    def test_a_span_resuming_at_the_end_across_unlisted_pages_adds_every_page_to_the_end(self) -> None:
        added = [page for page in range(6, PAGE_COUNT + 1) if page not in LISTED_PAGES]
        case = relisting_case(self, judged({"start": "5", "resume": "end"}), added)
        outcome = case.call("trial")
        self.assertEqual(("rescope", added), (outcome["state"], case.read("state.json")["named_pages"]))

    def test_pages_added_before_stay_listed_beside_new_ones(self) -> None:
        case = relisting_case(self, {"pages_judged": [*LISTED_PAGES, 12], "spans": [{**SEEN_SPAN, "see": [20]}]},
                              [12, 20], {"scope_runs": 1, "named_pages": [12]})
        case.put("scope.json", listing([*LISTED_PAGES, 12]))
        case.call("trial")
        self.assertEqual(("--page", "12", "--page", "20"), scope_options(case))

    def test_unseen_pages_on_the_last_scope_run_set_the_work_aside(self) -> None:
        outcome = relisting_case(self, judged({**SEEN_SPAN, "see": UNLISTED_SEE_PAGES}), UNLISTED_SEE_PAGES,
                                 {"scope_runs": 2}).call("trial")
        self.assertEqual("aside", outcome["state"])


class TestADoubtThePagesDoNotSettle(unittest.TestCase):
    def test_a_first_ambiguous_span_asks_for_a_new_scope_carrying_the_reason(self) -> None:
        outcome = trial_case(self, judged(DOUBTED_SPAN)).call("trial")
        self.assertEqual(("rescope", True), (outcome["state"], DOUBT_REASON in outcome["note"]))

    def test_an_ambiguous_span_with_unseen_see_pages_lists_them_before_putting_the_doubt(self) -> None:
        case = relisting_case(self, judged({**DOUBTED_SPAN, "see": UNLISTED_SEE_PAGES}), UNLISTED_SEE_PAGES)
        outcome = case.call("trial")
        self.assertEqual((True, False), ("file pages 12, 13" in outcome["note"], DOUBT_REASON in outcome["note"]))

    def test_a_second_ambiguous_verdict_continues_to_the_extraction_keeping_the_stretch(self) -> None:
        case = trial_case(self, judged(DOUBTED_SPAN), state={"scope_runs": 1, "doubt_put": True})
        case.call("trial")
        self.assertIn("--exclude-nothing", extract_call(case))

    def test_a_second_ambiguous_verdict_records_the_kept_stretch_in_the_works_state(self) -> None:
        case = trial_case(self, judged(DOUBTED_SPAN), state={"scope_runs": 1, "doubt_put": True})
        case.call("trial")
        note = case.read("state.json")["scope_notes"][0]
        self.assertEqual((True, True), ("'3' to '4'" in note, DOUBT_REASON in note))

    def test_a_second_ambiguous_verdict_keeps_the_other_spans(self) -> None:
        case = trial_case(self, judged(DOUBTED_SPAN, {"start": "5", "resume": "6"}),
                          state={"scope_runs": 1, "doubt_put": True})
        case.call("trial")
        self.assertEqual(("--exclude", "5", "6"), extract_call(case)[3:])

    def test_a_doubt_on_the_last_scope_run_sets_the_work_aside(self) -> None:
        outcome = trial_case(self, judged(DOUBTED_SPAN), state={"scope_runs": 2}).call("trial")
        self.assertEqual("aside", outcome["state"])


class TestTrialVerification(unittest.TestCase):
    def verify(self, trial_text: str, spans: list[tuple[str, str]]) -> list[str]:
        trial = Path(self.enterContext(tempfile.TemporaryDirectory())) / "trial.md"
        trial.write_text(trial_text)
        return TrialVerification(CHAPTER_HEADINGS, spans).findings({"written": str(trial)})

    def test_headings_found_in_order_raise_nothing(self) -> None:
        self.assertEqual([], self.verify("# One\n## Inner\n# Two\n# Three\n", []))

    def test_a_heading_out_of_order_is_missing(self) -> None:
        self.assertEqual(["missing heading: 'Two' (file p. 10)"], self.verify("# Two\n# One\n## Inner\n# Three\n", []))

    def test_a_heading_inside_an_excluded_span_is_not_required(self) -> None:
        self.assertEqual([], self.verify("# One\n# Two\n# Three\n", [("5", "6")]))

    def test_a_heading_inside_a_span_resuming_at_the_end_is_not_required(self) -> None:
        self.assertEqual([], self.verify("# One\n## Inner\n# Two\n", [("20: Three", "end")]))


def accepting_case(test: unittest.TestCase, verdicts: dict | None = None, state: dict | None = None,
                   labels: ScriptRun | None = None, trial_text: str = "# One\n## Inner\n# Two\n# Three\n") -> BackfillCase:
    script = StubScript({"labels": labels} if labels else {})
    case = trial_case(test, verdicts or judged(), script, state)
    case.put("probe.json", {"headings": CHAPTER_HEADINGS, "page_count": PAGE_COUNT})
    (case.work_dir / "trial.md").write_text(trial_text)
    script.results["extract"] = ScriptRun(0, json.dumps({"written": str(case.work_dir / "trial.md")}))
    return case


class TestATrialIsAcceptedWithoutAReview(unittest.TestCase):
    def test_an_extracted_trial_is_accepted_and_labelled(self) -> None:
        case = accepting_case(self)
        outcome = case.call("trial")
        commands = [call[0] for call in case.script.calls if call[0] in ("accept", "labels")]
        self.assertEqual(("accepted", ["accept", "labels", "labels"]), (outcome["state"], commands))

    def test_a_kept_doubted_stretch_reaches_the_accepted_notes(self) -> None:
        case = accepting_case(self, judged(DOUBTED_SPAN), {"scope_runs": 1, "doubt_put": True})
        self.assertTrue(any("'3' to '4'" in note for note in case.call("trial")["notes"]))

    def test_a_missing_heading_is_noted_and_never_holds_the_work(self) -> None:
        outcome = accepting_case(self, trial_text="# One\n# Three\n").call("trial")
        self.assertEqual("accepted", outcome["state"])
        self.assertIn("missing heading: 'Inner' (file p. 5)", outcome["notes"])

    def test_an_uncitable_work_is_accepted_without_labels(self) -> None:
        uncitable = ScriptRun(1, "", "uncitable: the corpus file carries uncitable:")
        outcome = accepting_case(self, labels=uncitable).call("trial")
        self.assertEqual(("accepted", True), (outcome["state"], "uncitable: no labels" in outcome["notes"]))


class TestDriverOutcome(unittest.TestCase):
    def test_a_failed_step_becomes_an_aside_question(self) -> None:
        case = BackfillCase(self, StubScript({"probe": ScriptRun(1, "", "no such PDF")}))
        outcome = case.call("prep")
        self.assertEqual(("aside", PDF, "probe failed: no such PDF"),
                         (outcome["state"], outcome["pdf"], outcome["question"]))


NOT_IN_CACHE = "huggingface_hub.errors.LocalEntryNotFoundError: cannot find the requested files in the disk cache"
RECORDS_UNPARSABLE = "library/extraction-records.json is not valid JSON (Expecting value: line 1)"
REQUESTS_FAILED = "engine_guard.FailedInferenceRequests: 12 engine requests failed after their retries"


class TestFailuresThatRecurOnEveryWork(unittest.TestCase):
    def test_a_model_missing_from_the_cache_halts_the_batch_at_the_trial(self) -> None:
        case = trial_case(self, judged(), StubScript({"extract": ScriptRun(1, "", NOT_IN_CACHE)}))
        self.assertEqual("halt", case.call("trial")["state"])

    def test_an_unparsable_extraction_records_file_halts_the_batch_at_the_trial(self) -> None:
        case = trial_case(self, judged(), StubScript({"extract": ScriptRun(1, "", RECORDS_UNPARSABLE)}))
        self.assertEqual("halt", case.call("trial")["state"])

    def test_a_model_missing_from_the_cache_halts_the_batch_at_the_preparation(self) -> None:
        case = BackfillCase(self, StubScript({"probe": ScriptRun(1, "", NOT_IN_CACHE)}))
        self.assertEqual("halt", case.call("prep")["state"])

    def test_engine_requests_failing_halt_the_batch_at_the_trial(self) -> None:
        case = trial_case(self, judged(), StubScript({"extract": ScriptRun(1, "", REQUESTS_FAILED)}))
        self.assertEqual("halt", case.call("trial")["state"])

    def test_engine_requests_failing_halt_the_batch_at_the_preparation(self) -> None:
        script = probed()
        script.results["convert"] = ScriptRun(1, "", REQUESTS_FAILED)
        case = BackfillCase(self, script)
        case.invoke("fonts-checked")
        self.assertEqual("halt", case.call("prep")["state"])

    def test_a_failure_of_one_work_still_sets_it_aside(self) -> None:
        case = trial_case(self, judged(), StubScript({"extract": ScriptRun(1, "", "the PDF is missing")}))
        self.assertEqual("aside", case.call("trial")["state"])


class TestDetachedEngineStep(unittest.TestCase):
    def test_an_engine_step_still_running_after_its_wait_reports_running(self) -> None:
        case = BackfillCase(self, StubScript(), RecordingLauncher())
        case.probe.alive = True
        outcome = case.invoke("trial")
        self.assertEqual(("running", PDF, [("trial", 1)], str(STEP_PID)),
                         (outcome["state"], outcome["pdf"], case.launcher.launches,
                          (case.work_dir / "step.pid").read_text()))

    def test_a_live_step_refuses_a_second_start(self) -> None:
        case = BackfillCase(self, StubScript(), RecordingLauncher())
        case.probe.alive = True
        case.invoke("prep")
        self.assertEqual(("running", 1), (case.invoke("trial")["state"], len(case.launcher.launches)))

    def test_wait_returns_the_finished_step_and_keeps_its_result_for_a_repeated_wait(self) -> None:
        case = BackfillCase(self, StubScript({"probe": ScriptRun(1, "", "no such PDF")}))
        outcome = case.call("prep")
        self.assertEqual(("aside", False, outcome), (outcome["state"], (case.work_dir / "step.pid").exists(),
                                                      case.invoke("wait")))

    def test_wait_reports_running_once_its_timeout_passes(self) -> None:
        case = BackfillCase(self, StubScript(), RecordingLauncher())
        case.probe.alive = True
        case.invoke("prep")
        step = DetachedStep(BackfillQueue(case.work_dir.parents[1]).work(1), case.host)
        self.assertEqual(("running", True), (step.wait(SHORT_WAIT_SECONDS)["state"],
                                             SHORT_WAIT_SECONDS <= case.clock.elapsed))

    def test_a_step_that_died_with_no_result_sets_the_work_aside(self) -> None:
        case = BackfillCase(self, StubScript(), RecordingLauncher())
        case.invoke("prep")
        outcome = case.invoke("wait")
        self.assertEqual(("aside", "the driver step ended with no result"), (outcome["state"], outcome["question"]))


def probed(**fields) -> StubScript:
    probe = {"headings": CHAPTER_HEADINGS, "page_count": PAGE_COUNT, **fields}
    return StubScript({"probe": ScriptRun(0, json.dumps(probe)), "scope": ScriptRun(0, json.dumps(listing(LISTED_PAGES)))})


def called_commands(case: BackfillCase) -> list[str]:
    return [call[0] for call in case.script.calls]


class TestFontRepairBeforeConversion(unittest.TestCase):
    def test_a_work_without_a_font_check_asks_for_the_repair_before_converting(self) -> None:
        case = BackfillCase(self, probed())
        self.assertEqual(("fonts", ["probe"]), (case.call("prep")["state"], called_commands(case)))

    def test_a_recorded_font_check_lets_the_preparation_convert(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("fonts-checked")
        self.assertEqual(("ready", ["probe", "convert", "scope"]), (case.call("prep")["state"], called_commands(case)))

    def test_the_font_check_survives_the_preparation(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("fonts-checked")
        case.call("prep")
        self.assertTrue(case.read("state.json")["fonts_checked"])

    def test_recording_the_font_check_keeps_the_works_state(self) -> None:
        case = BackfillCase(self, probed())
        case.put("state.json", {"flags": ["--force-ocr"], "scope_runs": 1})
        self.assertEqual("fonts-checked", case.invoke("fonts-checked")["state"])
        self.assertEqual({"flags": ["--force-ocr"], "scope_runs": 1, "fonts_checked": True}, case.read("state.json"))

    def test_a_work_carrying_a_body_skips_without_asking_for_the_repair(self) -> None:
        case = BackfillCase(self, probed(body_exists=True))
        self.assertEqual("skip", case.call("prep")["state"])

    def test_a_reviewed_work_skips_without_asking_for_the_repair(self) -> None:
        case = BackfillCase(self, probed(reviewed="2026-01-01"))
        self.assertEqual("skip", case.call("prep")["state"])


class TestBackfillQueue(unittest.TestCase):
    def test_a_work_listed_under_another_key_keeps_its_own_directory(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        listed = ListedWorks(directory / "ingest")
        queue = BackfillQueue(directory / "backfill")
        listed.list(1, PDF)
        first = queue.work(1).directory.resolve()
        listed.list(2, PDF)
        self.assertEqual(first, queue.work(2).directory.resolve())


if __name__ == "__main__":
    unittest.main()
