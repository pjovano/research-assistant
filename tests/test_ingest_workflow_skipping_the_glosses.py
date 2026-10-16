from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const steps = []
const onBibliographies = task => task()
async function drive(line) { steps.push(line.step); return { state: 'nothing' } }
async function parallel(tasks) { return Promise.all(tasks.map(task => task())) }
async function glossOne() { return { state: 'glossed' } }
"""


class TestSkippingTheGlosses(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations("gloss")

    def glossed(self, given: dict) -> dict:
        program = (f"const ARGS = {json.dumps(given)}\n{self.source}\n"
                   "gloss([1, 2]).then(line => console.log(JSON.stringify({ line, steps })))")
        return json.loads(self.runtime.printed(program))

    def test_gloss_none_plans_nothing_and_glosses_nothing(self) -> None:
        result = self.glossed({"gloss": "none"})
        self.assertEqual(([], {"glossed": [], "questions": []}), (result["steps"], result["line"]))

    def test_without_the_key_the_touched_bibliographies_are_planned(self) -> None:
        self.assertEqual(["drive-gloss-plan"], self.glossed({})["steps"])


if __name__ == "__main__":
    unittest.main()
