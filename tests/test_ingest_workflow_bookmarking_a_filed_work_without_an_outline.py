from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
class Paused extends Error {}
const SONNET = 'sonnet'
const BOOKMARKER_REPORT = {}
const prompts = []
const preps = []
let report = null
let lines = []
async function worker(stage, prompt, options) { prompts.push(prompt); return report }
async function extractDrive(step, key, extra) { preps.push(extra); return lines.shift() }
"""
REPORT = {"outcome": "built", "toc_found": False, "checklist": 0, "confirmed": 0, "unfound": [], "stopped_on": []}
READY = {"state": "ready", "parts": []}
UNBOOKMARKED = {"state": "unbookmarked", "question": "a book with no outline", "kind": "book", "pixels_only": False}
UNBOOKMARKED_ARTICLE = {**UNBOOKMARKED, "question": "a conferencePaper with no outline", "kind": "article"}


class TestBookmarkingAFiledWork(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = STUBS + WorkflowSource.ingest().declarations(
            "UNTRUSTED_LAYER_LINE", "ONE_CHAPTER_FLAG", "KIND_PHRASE", "libraryPdfLine",
            "aside", "WORKER_ATTEMPTS", "settledWorker", "reportOf", "bookmark", "bookmarkedFiled")

    def run_with(self, report: dict | None, *lines: dict, unbookmarked: dict = UNBOOKMARKED) -> dict:
        program = (f"{self.source}\nreport = {json.dumps(report)}\nlines = {json.dumps(list(lines))}\n"
                   f"bookmarkedFiled('7', 'work.json', {json.dumps(unbookmarked)}, [])"
                   f".then(line => console.log(JSON.stringify({{line, prompts, preps}})))")
        return json.loads(self.runtime.printed(program))

    def test_the_bookmarker_is_dispatched_on_the_library_pdf_as_a_book(self) -> None:
        prompt = self.run_with(REPORT, READY)["prompts"][0]
        self.assertEqual((True, True), ("in the library" in prompt, "Kind: a book." in prompt))

    def test_a_filed_article_is_dispatched_to_the_bookmarker_as_an_article(self) -> None:
        prompt = self.run_with(REPORT, READY, unbookmarked=UNBOOKMARKED_ARTICLE)["prompts"][0]
        self.assertEqual((True, False), ("Kind: an article." in prompt, "Kind: a book." in prompt))

    def test_an_outline_written_lets_the_preparation_run_again(self) -> None:
        ran = self.run_with(REPORT, READY)
        self.assertEqual(("ready", [""]), (ran["line"]["state"], ran["preps"]))

    def test_no_heading_found_extracts_the_work_as_one_chapter(self) -> None:
        ran = self.run_with({**REPORT, "outcome": "no-divisions"}, READY)
        self.assertEqual(("ready", ["--one-chapter"]), (ran["line"]["state"], ran["preps"]))

    def test_a_bookmarker_that_could_not_write_an_outline_sets_the_work_aside_at_stage_two(self) -> None:
        line = self.run_with({**REPORT, "outcome": "failed"})["line"]
        self.assertEqual(("aside", "extract"), (line["state"], line["stage"]))

    def test_a_work_still_without_an_outline_after_the_bookmarker_is_set_aside(self) -> None:
        self.assertEqual("aside", self.run_with(REPORT, UNBOOKMARKED)["line"]["state"])


if __name__ == "__main__":
    unittest.main()
