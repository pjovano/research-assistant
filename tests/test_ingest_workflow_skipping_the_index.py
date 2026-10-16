from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const steps = []
let halt = null
const TAIL_KEY = 'tail'
const SCRIPTS = { search: 'search.py' }
async function index() { steps.push('drive-index'); return { state: 'indexed', questions: [] } }
async function detached(stage, key, command) { steps.push(command); return { state: 'ran' } }
"""


class TestSkippingTheIndex(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations("synced")

    def synced(self, given: dict) -> dict:
        program = (f"const ARGS = {json.dumps(given)}\n{self.source}\n"
                   "synced().then(line => console.log(JSON.stringify({ line, steps })))")
        return json.loads(self.runtime.printed(program))

    def test_index_false_syncs_nothing_and_asks_nothing(self) -> None:
        result = self.synced({"index": False})
        self.assertEqual(([], {"questions": []}), (result["steps"], result["line"]))

    def test_without_the_key_the_search_stores_are_synced(self) -> None:
        self.assertEqual(["drive-index"], self.synced({})["steps"])


if __name__ == "__main__":
    unittest.main()
