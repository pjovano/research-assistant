from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from _support import PROJECT_ROOT

HOOK_SCRIPT = PROJECT_ROOT / "lib" / "harness_hooks.py"
OUTSIDE_THE_PIPELINE = json.dumps({"tool_input": {"command": "git status --porcelain"}})
MODULE_PATH_VARIABLES = ("PYTHONPATH", "PYTHONHOME")


def bare_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in MODULE_PATH_VARIABLES}


class TestTheHealthWatcherHookRunAsTheHarnessRunsIt(unittest.TestCase):
    def setUp(self) -> None:
        self.completed = subprocess.run([sys.executable, str(HOOK_SCRIPT), "ensure-health-watcher"],
                                        input=OUTSIDE_THE_PIPELINE, capture_output=True, text=True,
                                        env=bare_environment(), cwd=PROJECT_ROOT / "tests")

    def test_imports_the_core_with_only_lib_on_the_module_path(self) -> None:
        self.assertEqual("", self.completed.stderr)

    def test_lets_the_command_run(self) -> None:
        self.assertEqual((0, ""), (self.completed.returncode, self.completed.stdout))


if __name__ == "__main__":
    unittest.main()
