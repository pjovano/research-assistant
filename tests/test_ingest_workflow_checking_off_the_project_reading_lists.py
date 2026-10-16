from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

CHECKED_OFF = ["Kant: - [[Friedman - 1992 - Kant and the Exact Sciences]]"]
STUBS = """
const steps = []
let readLine = null
async function tailStep(step) { steps.push(step); return readLine }
"""


class TestTheWorkflowCheckingOffTheProjectReadingLists(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations("checkedOff")

    def read(self, line: dict) -> dict:
        program = (f"{self.source}\nreadLine = {json.dumps(line)}\n"
                   "checkedOff().then(read => console.log(JSON.stringify({ read, steps })))")
        return json.loads(self.runtime.printed(program))

    def test_the_tail_runs_the_reading_lists_step(self) -> None:
        self.assertEqual(["drive-readings"], self.read({"state": "read", "checked_off": [], "questions": []})["steps"])

    def test_a_read_line_carries_the_entries_checked_off(self) -> None:
        line = {"state": "read", "checked_off": CHECKED_OFF, "questions": []}
        self.assertEqual({"checked_off": CHECKED_OFF, "questions": []}, self.read(line)["read"])

    def test_a_step_set_aside_checks_nothing_off_and_asks_its_question(self) -> None:
        read = self.read({"state": "aside", "question": "drive-readings error"})["read"]
        self.assertEqual(([], ["the project reading lists were not read: drive-readings error"]),
                         (read["checked_off"], read["questions"]))


if __name__ == "__main__":
    unittest.main()
