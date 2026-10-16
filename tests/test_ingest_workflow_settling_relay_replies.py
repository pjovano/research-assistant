from __future__ import annotations

import json
import unittest

from _workflow_source import WORKFLOW, JsRuntime, WorkflowSource

EXPORT_PREFIX = "export "
COMMAND = "~/.research-vault/venv/bin/python ~/Developer/research-tools/.claude/skills/ingest/scripts/ingest.py drive-batch"
LONG_REPLY = "The working directory is not the repository. " * 20


class WorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = JsRuntime()
        self.runtime.require(self)
        self.source = WorkflowSource.ingest()


class TestTheWorkflowScript(WorkflowCase):
    def test_the_script_parses_as_a_workflow_body(self) -> None:
        body = WORKFLOW.read_text(encoding="utf-8").replace(EXPORT_PREFIX, "", 1)
        program = (f"const AsyncFunction = Object.getPrototypeOf(async function () {{}}).constructor\n"
                   f"new AsyncFunction('args', 'agent', 'parallel', 'phase', 'log', {json.dumps(body)})\n"
                   f"console.log('parsed')")
        self.assertEqual("parsed", self.runtime.printed(program))


class TestSettlingAReply(WorkflowCase):
    def settled(self, stage: str, state: str) -> str:
        source = self.source.declarations("WHOLE_BATCH_STAGES", "STOPPING_STATES", "settledReply")
        return self.runtime.value_of(source, f"settledReply({json.dumps(stage)}, {{state: {json.dumps(state)}}}).state")

    def test_an_aside_at_preflight_halts_the_batch(self) -> None:
        self.assertEqual("halt", self.settled("preflight", "aside"))

    def test_an_aside_in_the_tail_halts_the_batch(self) -> None:
        self.assertEqual("halt", self.settled("tail", "aside"))

    def test_an_unreadable_reply_at_preflight_halts_the_batch(self) -> None:
        self.assertEqual("halt", self.settled("preflight", "unreadable"))

    def test_an_unreadable_reply_at_a_works_stage_sets_it_aside(self) -> None:
        self.assertEqual("aside", self.settled("extract", "unreadable"))

    def test_an_unreadable_reply_set_aside_is_marked_unread(self) -> None:
        source = self.source.declarations("WHOLE_BATCH_STAGES", "STOPPING_STATES", "settledReply")
        self.assertTrue(self.runtime.value_of(source, "settledReply('shape', {state: 'unreadable'}).unread"))

    def test_an_aside_the_step_printed_is_not_marked_unread(self) -> None:
        source = self.source.declarations("WHOLE_BATCH_STAGES", "STOPPING_STATES", "settledReply")
        self.assertFalse(self.runtime.value_of(source, "Boolean(settledReply('shape', {state: 'aside'}).unread)"))

    def test_an_aside_at_a_works_stage_stays_aside(self) -> None:
        self.assertEqual("aside", self.settled("extract", "aside"))

    def test_a_ready_preflight_is_kept(self) -> None:
        self.assertEqual("ready", self.settled("preflight", "ready"))


class TestTheUnreadableQuestion(WorkflowCase):
    def question(self, reply: str) -> str:
        source = self.source.declarations("REPLY_OPENING_CHARS", "unreadable")
        return self.runtime.value_of(source, f"unreadable('drive-batch', {json.dumps(COMMAND)}, "
                                             f"{json.dumps(reply)}).question")

    def test_the_question_names_the_command_relayed(self) -> None:
        self.assertIn(COMMAND, self.question(LONG_REPLY))

    def test_the_question_keeps_the_replys_opening(self) -> None:
        self.assertIn(LONG_REPLY[:300], self.question(LONG_REPLY))

    def test_the_question_cuts_the_reply_after_its_opening(self) -> None:
        self.assertNotIn(LONG_REPLY[:301], self.question(LONG_REPLY))


if __name__ == "__main__":
    unittest.main()
