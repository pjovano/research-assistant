from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _ingest.citations import JudgeListings
from _ingest.cite import WorkCiteStep
from _ingest.tail import CiteStep

STERN = "Stern - 2023 - Understanding Hegel's Logic"
HOULGATE = "Houlgate - 2006 - The Opening of Hegel's Logic"
SYNCED = {"synced": 2, "removed": 0, "notes": 10}
NO_LISTINGS = JudgeListings(Path("no-middle-band"))


def rows(*written: str) -> ScriptRun:
    return ScriptRun(0, json.dumps([{"basename": basename, "status": "rewritten"} for basename in written]))


class RecordingScript(SkillScript):
    def __init__(self, replies: list[ScriptRun]) -> None:
        super().__init__(Path("script.py"))
        self._replies = list(replies)
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self._replies.pop(0)


def outcome(step) -> dict:
    return StepGuard("drive-cite").outcome(step.run)


class TestTheWorkCiteStep(unittest.TestCase):
    def setUp(self) -> None:
        self.cite = RecordingScript([rows(STERN), rows(HOULGATE)])
        self.graph = RecordingScript([ScriptRun(0, json.dumps(SYNCED))])

    def test_the_work_is_linked_outbound_then_inbound_then_synced(self) -> None:
        outcome(WorkCiteStep(STERN, self.cite, self.graph))
        self.assertEqual([("apply", STERN), ("apply", "--cited", STERN)], self.cite.calls)
        self.assertEqual([("sync", HOULGATE, STERN)], self.graph.calls)

    def test_the_line_names_every_corpus_file_written(self) -> None:
        line = outcome(WorkCiteStep(STERN, self.cite, self.graph))
        self.assertEqual({"state": "linked", "linked": [HOULGATE, STERN]}, line)

    def test_a_work_nothing_cites_syncs_itself_alone(self) -> None:
        cite = RecordingScript([rows(), rows()])
        outcome(WorkCiteStep(STERN, cite, self.graph))
        self.assertEqual([("sync", STERN)], self.graph.calls)

    def test_a_failed_apply_halts(self) -> None:
        cite = RecordingScript([ScriptRun(1, "the citation parser is not installed")])
        line = outcome(WorkCiteStep(STERN, cite, self.graph))
        self.assertEqual("halt", line["state"])
        self.assertIn("citation parser", line["question"])

    def test_a_failed_sync_halts(self) -> None:
        graph = RecordingScript([ScriptRun(1, "no such table")])
        self.assertEqual("halt", outcome(WorkCiteStep(STERN, self.cite, graph))["state"])


class TestTheTailSweepSyncsTheGraph(unittest.TestCase):
    def test_the_graph_is_synced_whole_after_the_sweep(self) -> None:
        status = ScriptRun(0, json.dumps({"conflict_copies": [], "rows": []}))
        cite, graph = RecordingScript([status]), RecordingScript([ScriptRun(0, json.dumps(SYNCED))])
        StepGuard("tail").outcome(CiteStep(cite, NO_LISTINGS, graph).run)
        self.assertEqual([("sync",)], graph.calls)

    def test_a_failed_whole_sync_halts(self) -> None:
        status = ScriptRun(0, json.dumps({"conflict_copies": [], "rows": []}))
        cite, graph = RecordingScript([status]), RecordingScript([ScriptRun(1, "locked")])
        self.assertEqual("halt", StepGuard("tail").outcome(CiteStep(cite, NO_LISTINGS, graph).run)["state"])


if __name__ == "__main__":
    unittest.main()
