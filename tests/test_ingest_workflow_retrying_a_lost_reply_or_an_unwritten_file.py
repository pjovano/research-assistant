from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
class Paused extends Error {}
const labels = []
let replies = []
function proceed(stage) {}
async function agent(prompt, options) {
  labels.push(options.label)
  const reply = replies.shift()
  if (reply instanceof Error) throw reply
  return reply
}
"""
JSON_LINE = '{"state": "accepted"}'


class WorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations(
            "PHASE_OF", "RELAY_ATTEMPTS", "UNWRITTEN", "WORKER_ATTEMPTS", "REPLY_OPENING_CHARS", "CODE_FENCE_LINE",
            "SURROUNDING_BACKTICKS", "jsonLineOf", "parsedReplyOf", "isJsonObject", "unreadable", "relay", "worker",
            "settledWorker", "reportOf", "writtenOnRedispatch")

    def ran(self, replies: str, call: str) -> dict:
        program = (f"{self.source}\nreplies = {replies};\n"
                   f"{call}.then(value => console.log(JSON.stringify({{ value, labels }})))")
        return json.loads(self.runtime.printed(program))


class TestALostReplyAtAPerWorkStep(WorkflowCase):
    def test_the_step_is_relayed_again(self) -> None:
        ran = self.ran(json.dumps(["no line here", JSON_LINE]), "relay('drive-trial 22', 'drive-trial 22', 'Extract', RELAY_ATTEMPTS)")
        self.assertEqual(("accepted", ["drive-trial 22", "drive-trial 22, relayed again"]),
                         (ran["value"]["state"], ran["labels"]))

    def test_a_second_lost_reply_is_unreadable(self) -> None:
        ran = self.ran(json.dumps(["no line", "no line"]), "relay('drive-trial 22', 'drive-trial 22', 'Extract', RELAY_ATTEMPTS)")
        self.assertEqual("unreadable", ran["value"]["state"])


class TestTheStepsRelayedAgain(WorkflowCase):
    def relayed_again(self, stage: str) -> bool:
        stages = WorkflowSource.ingest().declarations("STAGES", "RELAYED_AGAIN_STAGES")
        return self.runtime.value_of(stages, f"RELAYED_AGAIN_STAGES.has({json.dumps(stage)})")

    def test_a_per_work_step_is_relayed_again(self) -> None:
        self.assertTrue(self.relayed_again("extract"))

    def test_preflight_is_relayed_again(self) -> None:
        self.assertTrue(self.relayed_again("preflight"))

    def test_a_tail_step_is_not_relayed_again(self) -> None:
        self.assertFalse(self.relayed_again("tail"))


class TestAWorkerThatReportsNothing(WorkflowCase):
    def test_a_missing_report_dispatches_the_worker_again(self) -> None:
        ran = self.ran(json.dumps([None, {"outcome": "built"}]), "reportOf('clean', 'p', { label: 'pdf-bookmarker' })")
        self.assertEqual(({"outcome": "built"}, ["pdf-bookmarker", "pdf-bookmarker, dispatched again"]),
                         (ran["value"], ran["labels"]))

    def test_a_failed_dispatch_dispatches_the_worker_again(self) -> None:
        ran = self.ran("[new Error('content filter'), {outcome: 'built'}]",
                       "reportOf('clean', 'p', { label: 'pdf-bookmarker' })")
        self.assertEqual({"outcome": "built"}, ran["value"])

    def test_two_missing_reports_report_nothing(self) -> None:
        self.assertIsNone(self.ran("[null, null]", "reportOf('clean', 'p', { label: 'pdf-bookmarker' })")["value"])


class TestAFileAWorkerNeverWrote(WorkflowCase):
    def redispatched(self, *lines: dict) -> dict:
        call = (f"(() => {{ const lines = {json.dumps(list(lines))}; let dispatches = 0;"
                f" return writtenOnRedispatch(async () => lines.shift(), async () => {{ dispatches++ }})"
                f".then(line => ({{ line, dispatches }})) }})()")
        return self.ran("[]", call)["value"]

    def test_the_worker_is_dispatched_again_and_the_step_run_again(self) -> None:
        ran = self.redispatched({"state": "unwritten", "question": "q"}, {"state": "review"})
        self.assertEqual(("review", 1), (ran["line"]["state"], ran["dispatches"]))

    def test_a_file_unwritten_twice_sets_the_work_aside(self) -> None:
        ran = self.redispatched({"state": "unwritten", "question": "q"}, {"state": "unwritten", "question": "q"})
        self.assertEqual("aside", ran["line"]["state"])

    def test_a_written_file_runs_the_step_once(self) -> None:
        self.assertEqual(0, self.redispatched({"state": "review"})["dispatches"])


if __name__ == "__main__":
    unittest.main()
