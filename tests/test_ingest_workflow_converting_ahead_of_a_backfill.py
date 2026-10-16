from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

STUBS = """
const SCRIPTS = { extract: 'extract.py' }
const relayed = []
let reply = { state: 'running' }
class Paused extends Error {}
async function drive(call) { relayed.push(call); return reply }
"""
BACKFILL_WORKS = [{"key": 3, "from": "extract"}, {"key": 4, "from": "extract"}]


class ConvertAheadCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.declarations = WorkflowSource.ingest().declarations("PREFETCH_KEY", "AWAIT_FONTS_FLAG", "convertAhead",
                                                                 "convertAheadQuestions")

    def started(self, origin: str, works: list[dict], reply: dict | None = None) -> dict:
        program = (f"const FROM = {json.dumps(origin)}\n{STUBS}\n{self.declarations}\n"
                   f"reply = {json.dumps(reply or {'state': 'running'})}\n"
                   f"convertAhead({json.dumps(works)}).then(started => console.log(JSON.stringify("
                   f"{{ relayed, questions: convertAheadQuestions(started) }})))")
        return json.loads(self.runtime.printed(program))


class TestConvertingAheadOfABackfill(ConvertAheadCase):
    def test_a_backfill_starts_one_detached_prefetch_over_the_runs_keys_awaiting_each_font_repair(self) -> None:
        relayed = self.started("extract", BACKFILL_WORKS)["relayed"]
        self.assertEqual([("drive-detach", "prefetch", "-- extract.py prefetch --await-fonts --keys 3 4")],
                         [(call["step"], call["target"], call["extra"]) for call in relayed])

    def test_the_prefetch_is_started_through_the_ingest_script(self) -> None:
        self.assertEqual("ingest", self.started("extract", BACKFILL_WORKS)["relayed"][0]["script"])

    def test_a_batch_from_the_inbox_starts_no_prefetch(self) -> None:
        self.assertEqual([], self.started("clean", [{"key": 1, "from": "clean"}])["relayed"])

    def test_a_backfill_of_no_works_starts_no_prefetch(self) -> None:
        self.assertEqual([], self.started("extract", [])["relayed"])

    def test_a_running_prefetch_asks_nothing(self) -> None:
        self.assertEqual([], self.started("extract", BACKFILL_WORKS)["questions"])

    def test_a_prefetch_that_did_not_start_is_a_question_of_the_report(self) -> None:
        reply = {"state": "aside", "question": "no command given"}
        questions = self.started("extract", BACKFILL_WORKS, reply)["questions"]
        self.assertEqual(["the conversion ahead of the run did not start: no command given"], questions)


if __name__ == "__main__":
    unittest.main()
