from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import harness_hooks
from _drive.detached import DetachedLauncher, ProcessProbe, StepHost, SystemClock
from _drive.work import IngestWorks
from _ingest.detach import DetachedCommand, DetachedSteps

PDF = "scan.pdf"
TAIL = "tail"
STEP_PID = 4242
RELAYED_REBUILD = ("~/.research-vault/venv/bin/python .claude/skills/ingest/scripts/ingest.py drive-detach tail -- "
                   "~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py sync --rebuild")


def python_printing(*lines: str, exit_code: int = 0) -> DetachedCommand:
    program = "".join(f"print({line!r});" for line in lines) + f"raise SystemExit({exit_code})"
    return DetachedCommand(["--", sys.executable, "-c", program])


class InlineLauncher(DetachedLauncher):
    def __init__(self) -> None:
        super().__init__(Path("ingest.py"))
        self.steps: DetachedSteps | None = None
        self.launches: list[tuple[str, ...]] = []

    def launch(self, *arguments: str | int) -> int:
        self.launches.append(tuple(str(argument) for argument in arguments))
        self.steps.run(str(arguments[0]), DetachedCommand([str(word) for word in arguments[1:]]))
        return STEP_PID


class DeadProbe(ProcessProbe):
    def is_alive(self, pid: int) -> bool:
        return False


class DetachCase(unittest.TestCase):
    def setUp(self) -> None:
        self.works_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.launcher = InlineLauncher()
        self.steps = DetachedSteps(IngestWorks(self.works_dir), StepHost(self.launcher, DeadProbe(), SystemClock()))
        self.launcher.steps = self.steps

    def ran(self, key: str, command: DetachedCommand) -> dict:
        self.steps.start(key, command)
        return self.steps.wait(key)


class TestADetachedStep(DetachCase):
    def test_launches_the_command_after_the_separator_under_its_key(self) -> None:
        command = python_printing('{"state": "bookmark"}')
        self.steps.start(PDF, command)
        self.assertEqual((PDF, "--", *command.words), self.launcher.launches[0])

    def test_hands_over_the_commands_last_json_line(self) -> None:
        outcome = self.ran(PDF, python_printing("scanning", '{"state": "glyphs", "groups": []}'))
        self.assertEqual({"state": "glyphs", "groups": []}, outcome)

    def test_keeps_only_its_result_in_the_keys_batch_work_directory(self) -> None:
        self.ran(PDF, python_printing('{"state": "bookmark"}'))
        self.assertEqual(["step.json"], sorted(path.name for path in (self.works_dir / Path(PDF).stem).iterdir()))

    def test_a_command_that_prints_no_json_line_and_succeeds_has_run(self) -> None:
        self.assertEqual({"state": "ran"}, self.ran(TAIL, python_printing("synced 3 notes")))

    def test_a_command_that_prints_no_json_line_and_fails_is_set_aside_with_its_output(self) -> None:
        outcome = self.ran(TAIL, python_printing("the store is locked", exit_code=1))
        self.assertEqual(("aside", True), (outcome["state"], "the store is locked" in outcome["question"]))

    def test_a_step_that_ends_with_no_result_is_set_aside(self) -> None:
        self.launcher.launch = lambda *arguments: STEP_PID
        self.steps.start(TAIL, python_printing("{}"))
        self.assertEqual("aside", self.steps.wait(TAIL)["state"])


class TestTheRelayedCommand(unittest.TestCase):
    def test_a_detached_rebuild_still_asks_for_permission(self) -> None:
        self.assertIsNotNone(harness_hooks.BashGuard(RELAYED_REBUILD).decision())


if __name__ == "__main__":
    unittest.main()
