from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import FIXTURES_DIR, LiveTree

LiveTree.activate()

import machine_health as health
from _health.job import VENV_PYTHON
from agent_core._adapters.host.launchd import LaunchdScheduler

FORMER_LAUNCH_AGENT = FIXTURES_DIR / "health-launch-agent.plist"
PLACEHOLDERS = ("@PYTHON@", "@SCRIPT@", "@LOG@")


class FormerLaunchAgent:
    def __init__(self, python: Path, script: Path, log: Path) -> None:
        self._values = (python, script, log)

    def contents(self) -> str:
        text = FORMER_LAUNCH_AGENT.read_text(encoding="utf-8")
        for placeholder, value in zip(PLACEHOLDERS, self._values):
            text = text.replace(placeholder, str(value))
        return text


class TestTheHealthJobOnTheCoresLaunchdScheduler(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.script = directory / "health.py"
        self.log = directory / "launchd.log"
        self.scheduler = LaunchdScheduler(directory / "LaunchAgents")

    def test_builds_the_former_launch_agents_bytes_from_its_label_and_contents(self) -> None:
        job = health.HealthJob(self.script, self.log).job()
        expected = FormerLaunchAgent(VENV_PYTHON, self.script, self.log).contents()
        self.assertEqual(expected.encode(), self.scheduler.definition(job).encode())

    def test_keeps_the_label_of_its_own(self) -> None:
        self.assertEqual("com.research-assistant.machine-health", health.HealthJob(self.script, self.log).job().label)


if __name__ == "__main__":
    unittest.main()
