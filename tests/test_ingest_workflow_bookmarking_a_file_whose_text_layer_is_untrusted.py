from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
class Paused extends Error {}
const SONNET = 'sonnet'
const BOOKMARKER_REPORT = {}
const prompts = []
async function worker(stage, prompt, options) {
  prompts.push(prompt)
  return { outcome: 'built', toc_found: true, checklist: 1, confirmed: 1, unfound: [], stopped_on: [] }
}
"""
UNTRUSTED = "The text layer of this file cannot be trusted"


class TestTheBookmarkerPrompt(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations(
            "UNTRUSTED_LAYER_LINE", "KIND_PHRASE", "inboxPdfLine", "aside", "WORKER_ATTEMPTS", "settledWorker", "reportOf", "bookmark")

    def prompt(self, pixels_only: bool) -> str:
        program = (f"{self.source}\nbookmark(inboxPdfLine('work.json'), 'book', {json.dumps(pixels_only)})"
                   f".then(() => console.log(JSON.stringify(prompts[0])))")
        return json.loads(self.runtime.printed(program))

    def test_a_file_read_from_pixels_tells_the_bookmarker_its_text_layer_is_untrusted(self) -> None:
        self.assertIn(UNTRUSTED, self.prompt(True))

    def test_a_repaired_file_says_nothing_of_its_text_layer(self) -> None:
        self.assertNotIn(UNTRUSTED, self.prompt(False))


if __name__ == "__main__":
    unittest.main()
