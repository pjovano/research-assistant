from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

WORK = "/scratch/backfill/works/by-key/7"
STUBS = """
const SONNET = 'sonnet'
const dispatched = []
const steps = []
let lines = []
async function worker(stage, prompt, options) { dispatched.push({ agentType: options.agentType, prompt }) }
async function prepared(key, notes, cleaned) { return lines.shift() }
async function extractDrive(step, key, extra) { steps.push([step, extra]); return lines.shift() }
"""
DECLARATIONS = ("MAX_LOOPS", "SCOPE_NOTE_OPENING", "SCOPE_DISPATCH_STATES", "NUMBER_SLOT", "COUNT_FIELD", "numbered",
                "scope", "cleanUp", "carry")


def parts(stem: str, count: int, tag: str) -> dict:
    return {"count": count, "listing": f"{stem}-part-{{n}}.json", "verdicts": f"{stem}-verdicts-{tag}-{{n}}.json"}


def listings(line: dict) -> list[str]:
    return [f"{WORK}/{line['parts']['listing'].replace('{n}', str(number))}"
            for number in range(1, line["parts"]["count"] + 1)]


READY = {"state": "ready", "pdf": "A.pdf", "dir": WORK, "parts": parts("scope", 2, "0")}
ACCEPTED = {"state": "accepted", "notes": []}
CLEANUP = {"state": "cleanup", "dir": WORK, "parts": parts("cleanup", 2, "1")}


class TestDispatchingOneWorkerPerListingPart(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations(*DECLARATIONS)

    def carried(self, *lines: dict) -> dict:
        program = (f"{self.source}\nlines = {json.dumps(list(lines))}\n"
                   f"carry('7', 'work.json', [], {{ cleaned: false }}).then(line => console.log(JSON.stringify({{ line, dispatched, steps }})))")
        return json.loads(self.runtime.printed(program))

    def prompts_to(self, result: dict, agent_type: str) -> list[str]:
        return [item["prompt"].splitlines()[0] for item in result["dispatched"] if item["agentType"] == agent_type]

    def test_each_scope_part_goes_to_a_section_scoper(self) -> None:
        result = self.carried(READY, ACCEPTED)
        self.assertEqual([f"Scope listing: {listing}" for listing in listings(READY)],
                         self.prompts_to(result, "section-scoper"))

    def test_an_accepted_trial_ends_the_work_without_a_review(self) -> None:
        result = self.carried(READY, ACCEPTED)
        self.assertEqual(([["drive-trial", None]], "accepted"), (result["steps"], result["line"]["state"]))

    def test_each_cleanup_part_goes_to_a_layout_corrector(self) -> None:
        result = self.carried(READY, CLEANUP, ACCEPTED)
        self.assertEqual([f"Correction listing: {listing}" for listing in listings(CLEANUP)],
                         self.prompts_to(result, "layout-corrector"))

    def test_the_cleanup_applies_its_corrections_before_the_work_ends(self) -> None:
        result = self.carried(READY, CLEANUP, ACCEPTED)
        self.assertEqual([["drive-trial", None], ["drive-cleanup", None]], result["steps"])

    def test_a_rejudging_sends_its_parts_to_section_scopers(self) -> None:
        rejudge = {"state": "rejudge", "dir": WORK, "parts": parts("scope-repair", 1, "0-repair-1")}
        result = self.carried(READY, rejudge, ACCEPTED)
        self.assertEqual(f"Scope listing: {listings(rejudge)[0]}", self.prompts_to(result, "section-scoper")[-1])


if __name__ == "__main__":
    unittest.main()
