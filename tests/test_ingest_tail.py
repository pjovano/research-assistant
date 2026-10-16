from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _rag.sync import SyncProgress
from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _ingest.citations import LISTING_NAME, JudgeListings
from _ingest.tail import AUTHOR_PROPOSALS, CheckStep, CiteStep, IndexStep

MODEL = "qwen3-embedding:4b"
CONSISTENT = {"consistent": True, "embedding_model": MODEL, "recorded_embedding_model": MODEL}
DISAGREEING = {**CONSISTENT, "consistent": False, "inconsistency": "manifest holds 3 chunk ids"}
MISMATCHED = {**CONSISTENT, "consistent": False, "recorded_embedding_model": "nomic-embed-text",
              "inconsistency": "the embedding store holds vectors from nomic-embed-text"}
SYNCED = {"changed": [], "skipped": ["A"], "pruned": [], "unreadable": [], "embedded_chunks": 0}
LIMIT_SECONDS = 3600


def json_run(payload: object, returncode: int = 0) -> ScriptRun:
    return ScriptRun(returncode, json.dumps(payload))


class StubScript(SkillScript):
    def __init__(self, results: dict[str, list[ScriptRun]]) -> None:
        super().__init__(Path("script.py"))
        self._results = {command: list(runs) for command, runs in results.items()}
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        runs = self._results[args[0]]
        return runs.pop(0) if len(runs) > 1 else runs[0]


class TimedOutSync(SkillScript):
    def __init__(self, progress: str) -> None:
        super().__init__(Path("search.py"), timeout_seconds=LIMIT_SECONDS)
        self._progress = progress

    def run(self, *args: str) -> ScriptRun:
        raise subprocess.TimeoutExpired(["search.py", *args], LIMIT_SECONDS, stderr=self._progress.encode("utf-8"))


def progress_of(changed: list[str], unchanged: list[str]) -> str:
    stream = io.StringIO()
    progress = SyncProgress(stream)
    for basename in unchanged:
        progress.unchanged(basename)
    for basename in changed:
        progress.changed(basename, children=4, embedded=4)
    return stream.getvalue()


def outcome(step) -> dict:
    return StepGuard("tail").outcome(step.run)


class TestCheck(unittest.TestCase):
    def test_a_clean_check_asks_nothing(self) -> None:
        line = outcome(CheckStep(StubScript({"check": [json_run({"blocking": {}, "advisory": {}})]})))
        self.assertEqual({"state": "checked", "questions": []}, line)

    def test_a_blocking_group_becomes_a_question_and_an_author_advisory_does_not(self) -> None:
        report = {"blocking": {"Placement": ["X: names [[Y]]"]},
                  "advisory": {AUTHOR_PROPOSALS: ["Hegel: 6 works"], "Backlog -- unplaced": ["Z"]}}
        line = outcome(CheckStep(StubScript({"check": [json_run(report, 1)]})))
        self.assertEqual(1, len(line["questions"]))
        self.assertIn("Placement", line["questions"][0])


def rows(*listed: dict) -> ScriptRun:
    return json_run({"conflict_copies": [], "rows": list(listed)})


class TestCite(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "citations"

    def sweep(self, script: StubScript) -> CiteStep:
        return CiteStep(script, JudgeListings(self.root))

    def test_changed_corpus_files_are_linked(self) -> None:
        script = StubScript({"status": [rows({"basename": "A", "status": "changed", "to_confirm": []})],
                             "apply": [json_run([])]})
        line = outcome(self.sweep(script))
        self.assertEqual(("linked", ["A"], ("apply",)), (line["state"], line["linked"], script.calls[1]))

    def test_nothing_changed_applies_nothing(self) -> None:
        script = StubScript({"status": [rows({"basename": "A", "status": "unchanged", "to_confirm": []})]})
        outcome(self.sweep(script))
        self.assertEqual([("status",)], script.calls)

    def test_a_middle_band_entry_goes_to_the_citation_judge_and_asks_nothing(self) -> None:
        item = {"entry": "Hegel, Logic", "basename": "Hegel - 1969 - Logic", "score": 80}
        script = StubScript({"status": [rows({"basename": "A", "status": "unchanged", "to_confirm": [item]})]})
        line = outcome(self.sweep(script))
        self.assertEqual(("judge", 1, []), (line["state"], line["count"], line["questions"]))

    def test_the_judge_listing_names_the_citing_work_the_entry_and_the_candidate(self) -> None:
        item = {"entry": "Hegel, Logic", "basename": "Hegel - 1969 - Logic", "score": 80}
        script = StubScript({"status": [rows({"basename": "A", "status": "unchanged", "to_confirm": [item]})]})
        outcome(self.sweep(script))
        listing = json.loads((self.root / "1" / LISTING_NAME).read_text(encoding="utf-8"))
        self.assertEqual([{"n": 0, "citing": "A", "entry": "Hegel, Logic", "candidate": "Hegel - 1969 - Logic",
                           "score": 80}], listing)

    def test_a_conflict_copy_halts_the_batch(self) -> None:
        script = StubScript({"status": [json_run({"conflict_copies": ["A 2.md"], "rows": []})]})
        self.assertEqual("halt", outcome(self.sweep(script))["state"])

    def test_the_citation_parser_unavailable_halts_the_batch(self) -> None:
        script = StubScript({"status": [ScriptRun(1, "", "the citation parser is not in the Hugging Face cache")]})
        self.assertEqual("halt", outcome(self.sweep(script))["state"])

    def test_a_failed_apply_halts_the_batch(self) -> None:
        script = StubScript({"status": [rows({"basename": "A", "status": "changed", "to_confirm": []})],
                             "apply": [ScriptRun(1, "", "Traceback")]})
        self.assertEqual("halt", outcome(self.sweep(script))["state"])


class TestIndex(unittest.TestCase):
    def test_an_agreeing_sync_is_indexed(self) -> None:
        line = outcome(IndexStep(StubScript({"sync": [json_run(SYNCED)], "status": [json_run(CONSISTENT)]})))
        self.assertEqual({"state": "indexed", "questions": []}, line)

    def test_changed_vectors_ask_the_user_to_reconnect_the_server(self) -> None:
        synced = {**SYNCED, "changed": ["A"]}
        line = outcome(IndexStep(StubScript({"sync": [json_run(synced)], "status": [json_run(CONSISTENT)]})))
        self.assertIn("vault-rag", line["questions"][0])

    def test_a_disagreement_is_synced_once_more(self) -> None:
        script = StubScript({"sync": [json_run(SYNCED)], "status": [json_run(DISAGREEING), json_run(CONSISTENT)]})
        self.assertEqual(("indexed", 2), (outcome(IndexStep(script))["state"],
                                          sum(call == ("sync",) for call in script.calls)))

    def test_a_disagreement_after_the_second_sync_halts_the_batch(self) -> None:
        script = StubScript({"sync": [json_run(SYNCED)], "status": [json_run(DISAGREEING)]})
        self.assertEqual("halt", outcome(IndexStep(script))["state"])

    def test_a_changed_embedding_model_asks_for_the_rebuild(self) -> None:
        refused = json_run({"error": "the embedding store holds vectors from nomic-embed-text"}, 1)
        script = StubScript({"sync": [refused], "status": [json_run(MISMATCHED)]})
        self.assertEqual("rebuild", outcome(IndexStep(script))["state"])

    def test_the_embedding_server_down_halts_the_batch(self) -> None:
        refused = json_run({"error": "Ollama is not running"}, 1)
        script = StubScript({"sync": [refused], "status": [json_run(CONSISTENT)]})
        self.assertEqual("halt", outcome(IndexStep(script))["state"])

    def test_a_sync_stopped_at_its_limit_after_indexing_works_is_indexed_with_a_question(self) -> None:
        line = outcome(IndexStep(TimedOutSync(progress_of(changed=["A", "B"], unchanged=["C"]))))
        self.assertEqual(("indexed", True), (line["state"], "after indexing 2 works" in line["questions"][0]))

    def test_a_sync_stopped_at_its_limit_before_indexing_a_work_halts_the_batch(self) -> None:
        self.assertEqual("halt", outcome(IndexStep(TimedOutSync(progress_of(changed=[], unchanged=["C"]))))["state"])

    def test_an_unreadable_note_becomes_a_question(self) -> None:
        synced = {**SYNCED, "unreadable": [{"basename": "A", "error": "bad YAML"}]}
        script = StubScript({"sync": [json_run(synced, 1)], "status": [json_run(CONSISTENT)]})
        self.assertIn("does not parse", outcome(IndexStep(script))["questions"][0])


if __name__ == "__main__":
    unittest.main()
