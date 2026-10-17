from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const relayed = []
const logged = []
const NOTES = 'notes.py'
async function relay(command) { relayed.push(command); return { accepted: ['Accepted idea'] } }
function log(line) { logged.push(line) }
"""
FOUND = {"tasks": [{"reviewed": "Idea", "thread": "focus", "title": "Further idea", "line": "- [x] #focus · a",
                    "state": "research"}]}
TASK = FOUND["tasks"][0]
UNATTENDED_RULE_OPENING = "This run is unattended"
ATTENDED_DELETION = "Delete those lines at step 8, and no other task."


class TheResolveTasksWorkflowRunningUnattended(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.declarations = WorkflowSource.resolve_tasks().declarations(
            "UNATTENDED_RULE", "acceptChecked", "researchPrompt", "reviewPrompt", "runLines")

    def run_with(self, unattended: bool) -> dict:
        program = (f"const unattended = {json.dumps(unattended)}\nconst found = {json.dumps(FOUND)}\n"
                   f"const ENRICH_STATE = 'enrich'\n{STUBS}\n{self.declarations}\n"
                   f"acceptChecked().then(acceptance => console.log(JSON.stringify({{ acceptance, relayed, "
                   f"research: researchPrompt({json.dumps(TASK)}), "
                   f"review: reviewPrompt('Idea', [{json.dumps(TASK)}]) }})))")
        return json.loads(self.runtime.printed(program))

    def test_an_unattended_run_relays_no_accept_and_accepts_no_note(self) -> None:
        outcome = self.run_with(True)
        self.assertEqual(([], []), (outcome["relayed"], outcome["acceptance"]["accepted"]))

    def test_an_attended_run_accepts_the_checked_notes(self) -> None:
        self.assertEqual(["notes.py accept --apply"], self.run_with(False)["relayed"])

    def test_an_unattended_run_passes_the_unattended_rule_to_each_note_researcher(self) -> None:
        self.assertIn(UNATTENDED_RULE_OPENING, self.run_with(True)["research"])

    def test_an_unattended_run_passes_the_unattended_rule_to_each_note_reviewer_and_deletes_no_task(self) -> None:
        review = self.run_with(True)["review"]
        self.assertEqual((True, False), (UNATTENDED_RULE_OPENING in review, ATTENDED_DELETION in review))

    def test_an_attended_run_passes_no_unattended_rule(self) -> None:
        outcome = self.run_with(False)
        self.assertEqual((False, False, True), (UNATTENDED_RULE_OPENING in outcome["research"],
                                                UNATTENDED_RULE_OPENING in outcome["review"],
                                                ATTENDED_DELETION in outcome["review"]))


if __name__ == "__main__":
    unittest.main()
