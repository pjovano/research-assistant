from __future__ import annotations

import unittest
from pathlib import Path

from _support import PROJECT_ROOT
from _workflow_source import JsRuntime, WorkflowSource

HOME_PREFIX = "~/"
SCRIPT_WORD = 1


class WorkflowCommands:
    def __init__(self, runtime: JsRuntime) -> None:
        source = WorkflowSource.ingest().declarations("PYTHON", "REPOSITORY", "SCRIPTS", "skillScript")
        self.repository = runtime.value_of(source, "REPOSITORY")
        self.commands = runtime.value_of(source, "SCRIPTS")

    def scripts(self) -> list[str]:
        return [command.split()[SCRIPT_WORD] for command in self.commands.values()]

    def in_this_checkout(self, script: str) -> Path:
        return PROJECT_ROOT / script.removeprefix(self.repository + "/")


class IngestCommandsResolvingFromAnyWorkingDirectory(unittest.TestCase):
    def setUp(self) -> None:
        runtime = JsRuntime()
        runtime.require(self)
        self.commands = WorkflowCommands(runtime)

    def test_every_script_is_named_from_the_home_directory(self) -> None:
        for script in self.commands.scripts():
            with self.subTest(script=script):
                self.assertTrue(script.startswith(HOME_PREFIX))

    def test_every_script_lies_under_the_repository(self) -> None:
        for script in self.commands.scripts():
            with self.subTest(script=script):
                self.assertTrue(script.startswith(self.commands.repository + "/"))

    def test_every_script_named_exists_in_the_checkout(self) -> None:
        for script in self.commands.scripts():
            with self.subTest(script=script):
                self.assertTrue(self.commands.in_this_checkout(script).is_file())


if __name__ == "__main__":
    unittest.main()
