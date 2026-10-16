from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _drive.script import TIMEOUT_SECONDS, SkillScript
from _extract.backfillrunner import ENGINE_STEP_TIMEOUT_SECONDS, ExtractScript

HOUR_SECONDS = 3600


def timeout_of(script: SkillScript) -> int:
    finished = subprocess.CompletedProcess([], 0, "{}", "")
    with mock.patch("_drive.script.subprocess.run", return_value=finished) as run:
        script.run("convert", "work.pdf")
    return run.call_args.kwargs["timeout"]


class TestEngineStepsOutlastingAnHour(unittest.TestCase):
    def test_an_engine_step_may_run_longer_than_an_hour(self) -> None:
        self.assertGreater(timeout_of(ExtractScript()), HOUR_SECONDS)

    def test_an_engine_step_takes_the_engine_steps_limit(self) -> None:
        self.assertEqual(ENGINE_STEP_TIMEOUT_SECONDS, timeout_of(ExtractScript()))

    def test_another_skill_script_keeps_the_ordinary_limit(self) -> None:
        self.assertEqual(TIMEOUT_SECONDS, timeout_of(SkillScript(mock.sentinel.script)))


if __name__ == "__main__":
    unittest.main()
