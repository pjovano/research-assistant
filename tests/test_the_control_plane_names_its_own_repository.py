from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

FORMER_NAME = "research" + "-tools"
OWN_NAME = "research" + "-assistant"
PLANNING_DIRECTORY = "upgrade"
NOTHING_FOUND = 1
FOUND = 0


class TrackedText:
    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root

    def lines_naming(self, name: str) -> list[str]:
        search = subprocess.run(["git", "grep", "-n", "-F", name, "--", ".", f":!{PLANNING_DIRECTORY}"],
                                cwd=self._root, capture_output=True, text=True)
        if search.returncode == NOTHING_FOUND:
            return []
        if search.returncode != FOUND:
            raise RuntimeError(f"git grep for {name!r} failed in {self._root}: {search.stderr.strip()}")
        return search.stdout.splitlines()


class TheControlPlaneNamesItsOwnRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.tracked = TrackedText(PROJECT_ROOT)

    def test_no_tracked_line_outside_the_plan_names_the_former_repository(self) -> None:
        self.assertEqual([], self.tracked.lines_naming(FORMER_NAME))

    def test_the_search_finds_the_repository_by_its_own_name(self) -> None:
        self.assertTrue(self.tracked.lines_naming(OWN_NAME))


if __name__ == "__main__":
    unittest.main()
