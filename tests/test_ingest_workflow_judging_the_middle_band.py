from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

ROOT = "/scratch/ingest/citations"
STUBS = """
const SONNET = 'sonnet'
const dispatched = []
const steps = []
async function parallel(tasks) { return Promise.all(tasks.map(task => task())) }
async function worker(stage, prompt, options) { dispatched.push({ stage, prompt, agentType: options.agentType }) }
async function onCitations(task) { return task() }
async function tailStep(step) { steps.push(step); return { state: 'settled', confirmed: 1, rejected: 1, questions: [] } }
"""


class TestJudgingTheMiddleBand(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations("judgedCitations")

    def judged(self, swept: dict) -> dict:
        program = (f"{self.source}\n"
                   f"judgedCitations({json.dumps(swept)}).then(line => "
                   f"console.log(JSON.stringify({{ line, dispatched, steps }})))")
        return json.loads(self.runtime.printed(program))

    def test_a_sweep_without_a_middle_band_dispatches_nobody(self) -> None:
        result = self.judged({"state": "linked", "linked": [], "questions": []})
        self.assertEqual(([], [], "linked"), (result["dispatched"], result["steps"], result["line"]["state"]))

    def test_each_listing_goes_to_a_citation_judge(self) -> None:
        result = self.judged({"state": "judge", "root": ROOT, "count": 2, "questions": []})
        self.assertEqual([("citation-judge", f"Listing: {ROOT}/1/listing.json"),
                          ("citation-judge", f"Listing: {ROOT}/2/listing.json")],
                         [(item["agentType"], item["prompt"].splitlines()[0]) for item in result["dispatched"]])

    def test_the_judges_answers_are_settled_once_they_are_written(self) -> None:
        result = self.judged({"state": "judge", "root": ROOT, "count": 2, "questions": []})
        self.assertEqual((["drive-settle"], "settled"), (result["steps"], result["line"]["state"]))


if __name__ == "__main__":
    unittest.main()
