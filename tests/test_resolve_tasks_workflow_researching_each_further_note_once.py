from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const dispatched = []
const research = new Map()
const REVIEW_STATE = 'review'
const ENRICH_STATE = 'enrich'
async function worker(prompt, agentType, label) {
  dispatched.push(label)
  return label.includes('Failing') ? { error: 'no report' } : { done: label, prompt }
}
function researchPrompt(task) { return task.title }
function reviewPrompt(note, resolved) { return resolved.map(task => task.title).join('|') }
"""
TASKS = [
    {"reviewed": "Idea", "thread": "focus", "title": "Shared", "line": "a", "state": "research"},
    {"reviewed": "Other idea", "thread": "conceptual", "title": "Shared", "line": "b", "state": "research"},
    {"reviewed": "Idea", "thread": "contrary", "title": "Failing", "line": "c", "state": "research"},
    {"reviewed": "Idea", "thread": "genealogical", "title": "Held", "line": "d", "state": "review"},
    {"reviewed": "Idea", "thread": "enrich", "title": "Idea", "line": "e", "state": "enrich"},
]


class TestResearchingEachFurtherNoteOnce(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.resolve_tasks().declarations(
            "reviewOnceResearched", "researchedOnce", "researchNote")

    def reviewed(self, notes: list[str]) -> dict:
        program = (f"const found = {{ tasks: {json.dumps(TASKS)} }}\n{self.source}\n"
                   f"Promise.all({json.dumps(notes)}.map(reviewOnceResearched))"
                   ".then(reviews => console.log(JSON.stringify({ reviews, dispatched })))")
        return json.loads(self.runtime.printed(program))

    def test_a_further_note_two_notes_chose_is_researched_once(self) -> None:
        dispatched = self.reviewed(["Idea", "Other idea"])["dispatched"]
        self.assertEqual(1, dispatched.count("research Shared"))

    def test_a_note_already_holding_references_is_not_researched_again(self) -> None:
        self.assertNotIn("research Held", self.reviewed(["Idea"])["dispatched"])

    def test_the_review_carries_only_the_tasks_whose_notes_were_researched(self) -> None:
        review = self.reviewed(["Idea"])["reviews"][0]
        self.assertEqual("Shared|Held|Idea", review["report"]["prompt"])

    def test_an_enrich_task_dispatches_no_researcher(self) -> None:
        self.assertNotIn("research Idea", self.reviewed(["Idea"])["dispatched"])

    def test_a_note_none_of_whose_further_notes_was_researched_is_not_reviewed(self) -> None:
        program_tasks = [task for task in TASKS if task["title"] == "Failing"]
        program = (f"const found = {{ tasks: {json.dumps(program_tasks)} }}\n{self.source}\n"
                   "reviewOnceResearched('Idea').then(review => console.log(JSON.stringify({ review, dispatched })))")
        result = json.loads(self.runtime.printed(program))
        self.assertEqual((["research Failing"], True),
                         (result["dispatched"], "skipped" in result["review"]))


if __name__ == "__main__":
    unittest.main()
