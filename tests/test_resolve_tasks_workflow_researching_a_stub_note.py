from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const dispatched = []
const unattended = false
async function worker(prompt, agentType, label) { dispatched.push({ prompt, agentType, label }); return { field: [] } }
"""


class TestResearchingAStubNote(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.resolve_tasks().declarations("researchStub", "runLines")

    def test_a_stub_note_is_researched_by_its_title_alone(self) -> None:
        program = (f"{self.source}\n"
                   "researchStub('An idea').then(report => console.log(JSON.stringify({ report, dispatched })))")
        result = json.loads(self.runtime.printed(program))
        self.assertEqual(({"note": "An idea", "field": []}, "note-researcher", "Research the atomic note titled: An idea"),
                         (result["report"], result["dispatched"][0]["agentType"], result["dispatched"][0]["prompt"]))


if __name__ == "__main__":
    unittest.main()
