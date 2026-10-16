from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

PARTS = "/scratch/ingest/reshape/parts"
ANSWERS = "/scratch/ingest/reshape/answers.json"
STUBS = """
const SONNET = 'sonnet'
const dispatched = []
const steps = []
let lines = {}
async function parallel(tasks) { return Promise.all(tasks.map(task => task())) }
async function worker(stage, prompt, options) { dispatched.push({ agentType: options.agentType, prompt }) }
async function onBibliographies(task) { return task() }
async function drive(line) { steps.push([line.step, line.target || null]); return lines[line.step] }
"""
LISTED = {"state": "shape", "dir": PARTS, "outcome": "/scratch/ingest/reshape/outcome.json",
          "parts": {"count": 3, "listing": "{n}/listing.json", "answers": "{n}/answers.json"}}
MERGED = {"state": "merged", "answers": ANSWERS, "parts": 3, "answered": 3}
RESHAPED = {"state": "reshaped", "created": ["X"], "moved": [], "linked": [], "unlinked": [], "added": [],
            "folded": [], "questions": []}


class TestDispatchingOneShaperPerListingPart(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        declarations = ("NUMBER_SLOT", "COUNT_FIELD", "numbered", "reshaped", "unreadReshaping")
        self.source = STUBS + WorkflowSource.ingest().declarations(*declarations)

    def shaped(self, merged: dict = MERGED) -> dict:
        lines = {"drive-clusters": LISTED, "drive-merge": merged, "drive-reshape": RESHAPED}
        program = (f"{self.source}\nlines = {json.dumps(lines)}\n"
                   "reshaped().then(shaped => console.log(JSON.stringify({ shaped, dispatched, steps })))")
        return json.loads(self.runtime.printed(program))

    def test_each_part_goes_to_a_bibliography_shaper_with_its_own_answers_path(self) -> None:
        prompts = [(item["agentType"], item["prompt"]) for item in self.shaped()["dispatched"]]
        self.assertEqual([("bibliography-shaper",
                           f"Listing: {PARTS}/{number}/listing.json\n"
                           f"Write your answers file to: {PARTS}/{number}/answers.json") for number in (1, 2, 3)],
                         prompts)

    def test_the_parts_answers_are_merged_before_the_merged_answers_are_applied(self) -> None:
        self.assertEqual([["drive-clusters", None], ["drive-merge", None], ["drive-reshape", ANSWERS]],
                         self.shaped()["steps"])

    def test_answers_that_did_not_merge_leave_the_bibliographies_unreshaped(self) -> None:
        result = self.shaped({"state": "aside", "question": "no part was answered"})
        self.assertEqual([["drive-clusters", None], ["drive-merge", None]], result["steps"])
        self.assertIn("not reshaped: no part was answered", result["shaped"]["questions"][0])


if __name__ == "__main__":
    unittest.main()
