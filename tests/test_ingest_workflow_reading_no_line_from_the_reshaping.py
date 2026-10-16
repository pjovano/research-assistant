from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

OUTCOME = "/scratch/ingest/reshape/outcome.json"
STUBS = """
const PARTS = { count: 2, listing: '{n}/listing.json', answers: '{n}/answers.json' }
const LINES = {
  'drive-clusters': { state: 'shape', dir: '/scratch/ingest/reshape/parts', parts: PARTS, outcome: '%s' },
  'drive-merge': { state: 'merged', answers: '/scratch/ingest/reshape/answers.json' },
}
let reshapeLine = null
async function drive(line) { return LINES[line.step] || reshapeLine }
async function worker() { return '' }
async function parallel(tasks) { return Promise.all(tasks.map(task => task())) }
async function onBibliographies(task) { return task() }
""" % OUTCOME


class TestTheWorkflowReadingNoLineFromTheReshaping(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        declarations = ("SONNET", "NUMBER_SLOT", "COUNT_FIELD", "numbered", "reshaped", "unreadReshaping")
        self.source = STUBS + WorkflowSource.ingest().declarations(*declarations)

    def shaped(self, line: dict) -> dict:
        program = (f"{self.source}\nreshapeLine = {json.dumps(line)}\n"
                   "reshaped().then(shaped => console.log(JSON.stringify(shaped)))")
        return json.loads(self.runtime.printed(program))

    def test_an_unread_line_never_reports_the_bibliographies_not_reshaped(self) -> None:
        question = self.shaped({"state": "aside", "unread": True, "question": "no JSON line"})["questions"][0]
        self.assertNotIn("not reshaped", question)

    def test_an_unread_line_names_the_file_recording_the_outcome(self) -> None:
        question = self.shaped({"state": "aside", "unread": True, "question": "no JSON line"})["questions"][0]
        self.assertIn(OUTCOME, question)

    def test_a_refused_reshaping_reports_the_bibliographies_not_reshaped(self) -> None:
        question = self.shaped({"state": "aside", "question": "the answers were refused"})["questions"][0]
        self.assertIn("not reshaped", question)

    def test_a_read_reshaping_carries_its_outcome(self) -> None:
        line = {"state": "reshaped", "created": ["X"], "moved": [], "linked": [], "unlinked": [], "added": [],
                "folded": [], "questions": []}
        self.assertEqual(["X"], self.shaped(line)["reshaped"]["created"])


if __name__ == "__main__":
    unittest.main()
