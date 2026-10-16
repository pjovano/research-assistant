from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _ingest.citations import ANSWERS_NAME, JudgedMatches, JudgeListings, SettleStep, VerdictsRecorder
from _ingest.cite import GraphRun

CITING = "Stern - 2023 - Understanding Hegel's Logic"
LOGIC = "Hegel - 2010 - The Science of Logic"
NATURE = "Hegel - 1970 - Philosophy of Nature"
RUN_SESSION = 4242
SYNCED = {"synced": 1, "removed": 0, "notes": 10}


def match(entry: str, candidate: str) -> dict:
    return {"citing": CITING, "entry": entry, "candidate": candidate, "score": 75.0}


class RecordingScript(SkillScript):
    def __init__(self, replies: list[ScriptRun]) -> None:
        super().__init__(Path("script.py"))
        self._replies = list(replies)
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self._replies.pop(0)


def settled(rewritten: list[str]) -> ScriptRun:
    rows = [{"basename": basename, "status": "rewritten"} for basename in rewritten]
    return ScriptRun(0, json.dumps({"recorded": 2, "not-offered": 0, "verdicts": [], "rows": rows}))


class SettleCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "citations"
        JudgeListings(self.root).write([match("Hegel, Science of Logic", LOGIC),
                                        match("Hegel, Encyclopedia Logic", NATURE)])

    def answer(self, *answers: dict) -> None:
        (self.root / "1" / ANSWERS_NAME).write_text(json.dumps(list(answers)), encoding="utf-8")

    def settle(self, cite: RecordingScript, graph: RecordingScript) -> dict:
        step = SettleStep(JudgedMatches(self.root), VerdictsRecorder(cite, RUN_SESSION), GraphRun(graph))
        return StepGuard("drive-settle").outcome(step.run)

    def verdicts_written(self) -> list[dict]:
        return json.loads(JudgedMatches(self.root).verdicts_path.read_text(encoding="utf-8"))


class TestTheJudgesVerdictsAreRecorded(SettleCase):
    def setUp(self) -> None:
        super().setUp()
        self.answer({"n": 0, "verdict": "confirm", "reason": "same work"},
                    {"n": 1, "verdict": "reject", "reason": "a different work"})
        self.cite = RecordingScript([settled([CITING])])
        self.graph = RecordingScript([ScriptRun(0, json.dumps(SYNCED))])
        self.line = self.settle(self.cite, self.graph)

    def test_each_verdict_names_the_citing_work_the_entry_and_the_candidate(self) -> None:
        self.assertEqual([("Hegel, Science of Logic", LOGIC, "confirm"), ("Hegel, Encyclopedia Logic", NATURE, "reject")],
                         [(item["entry"], item["work"], item["verdict"]) for item in self.verdicts_written()])

    def test_settle_records_them_inside_the_run_that_holds_the_lock(self) -> None:
        verdicts = str(JudgedMatches(self.root).verdicts_path)
        self.assertEqual([("settle", "--verdicts", verdicts, "--apply", "--in-run", str(RUN_SESSION))], self.cite.calls)

    def test_the_graph_is_synced_over_the_works_linked(self) -> None:
        self.assertEqual([("sync", CITING)], self.graph.calls)

    def test_the_settled_line_counts_the_verdicts_and_asks_nothing(self) -> None:
        self.assertEqual(("settled", 1, 1, []),
                         (self.line["state"], self.line["confirmed"], self.line["rejected"], self.line["questions"]))


class TestAMatchWithoutAVerdict(SettleCase):
    def test_a_match_the_judge_left_unanswered_is_not_recorded(self) -> None:
        self.answer({"n": 0, "verdict": "reject", "reason": "a different work"})
        self.settle(RecordingScript([settled([])]), RecordingScript([]))
        self.assertEqual([LOGIC], [item["work"] for item in self.verdicts_written()])

    def test_a_match_the_judge_left_unanswered_becomes_a_question(self) -> None:
        self.answer({"n": 0, "verdict": "reject", "reason": "a different work"})
        line = self.settle(RecordingScript([settled([])]), RecordingScript([]))
        self.assertEqual(1, len(line["questions"]))

    def test_an_answer_outside_confirm_and_reject_counts_as_unanswered(self) -> None:
        self.answer({"n": 0, "verdict": "unsure", "reason": "?"}, {"n": 1, "verdict": "reject", "reason": "x"})
        self.settle(RecordingScript([settled([])]), RecordingScript([]))
        self.assertEqual([NATURE], [item["work"] for item in self.verdicts_written()])

    def test_no_answers_file_records_nothing(self) -> None:
        cite = RecordingScript([])
        self.settle(cite, RecordingScript([]))
        self.assertEqual([], cite.calls)


class TestAFailedSettlement(SettleCase):
    def test_a_failed_settle_halts_the_batch(self) -> None:
        self.answer({"n": 0, "verdict": "confirm", "reason": "same work"})
        line = self.settle(RecordingScript([ScriptRun(1, "", "Traceback")]), RecordingScript([]))
        self.assertEqual("halt", line["state"])


class TestTheJudgeListings(unittest.TestCase):
    def listing_count(self, matches: int) -> int:
        listings = JudgeListings(Path(self.enterContext(tempfile.TemporaryDirectory())) / "citations")
        listings.write([match(f"entry {number}", LOGIC) for number in range(matches)])
        return listings.line([])["count"]

    def test_a_middle_band_of_a_hundred_and_twenty_fills_one_listing(self) -> None:
        self.assertEqual(1, self.listing_count(120))

    def test_a_long_middle_band_is_cut_into_listings_of_at_most_a_hundred_and_twenty(self) -> None:
        self.assertEqual(2, self.listing_count(121))

    def test_a_new_sweep_replaces_the_listings_of_the_last(self) -> None:
        root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "citations"
        listings = JudgeListings(root)
        listings.write([match(f"entry {number}", LOGIC) for number in range(61)])
        listings.write([match("entry", LOGIC)])
        self.assertEqual(1, listings.line([])["count"])


if __name__ == "__main__":
    unittest.main()
