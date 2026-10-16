from __future__ import annotations

import subprocess
import unittest

from _support import PROJECT_ROOT

CORE_HOST_DEFINITION = r"^\s*class (Scheduler|Notifier|SystemReadings|Job|Notice|Level)\b"
EXCLUDED_PATHS = (":(exclude)vendor/", ":(exclude)upgrade/")


class TrackedDefinitions:
    def __init__(self, pattern: str) -> None:
        self._pattern = pattern

    def lines(self) -> list[str]:
        completed = subprocess.run(["git", "grep", "-n", "-E", self._pattern, "--", ".", *EXCLUDED_PATHS],
                                   cwd=PROJECT_ROOT, capture_output=True, text=True)
        if completed.returncode > 1:
            raise RuntimeError(f"git grep failed in {PROJECT_ROOT}: {completed.stderr.strip()}")
        return completed.stdout.splitlines()


class TestNoModuleOfTheDomainDefinesACoreHostName(unittest.TestCase):
    def test_the_pattern_finds_a_definition(self) -> None:
        found = subprocess.run(["grep", "-E", CORE_HOST_DEFINITION], input="class Notifier(Protocol):\n",
                               capture_output=True, text=True).stdout
        self.assertTrue(found)

    def test_no_tracked_file_outside_the_vendored_core_and_the_plan_defines_one(self) -> None:
        self.assertEqual([], TrackedDefinitions(CORE_HOST_DEFINITION).lines())


if __name__ == "__main__":
    unittest.main()
