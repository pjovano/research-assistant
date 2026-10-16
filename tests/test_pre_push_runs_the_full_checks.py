import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

PRE_PUSH = Path(".githooks/pre-push")
AUDIT_SCRIPT = Path(".claude/skills/vault-audit/scripts/audit.py")
VENV = Path(".research-vault/venv")
REPOSITORY_LOCATING_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")
TEST_MODULE = "import unittest\n\n\nclass TestPush(unittest.TestCase):\n    def test_push(self):\n        {assertion}\n"
NAMED_WORK = {"file": "lib/x.py", "line": 4, "detail": "Doe - 2020 - A Work"}


class PushingTree:
    def __init__(self, root: Path, home: Path) -> None:
        self._root = root
        self._home = home
        self._install_the_hook()
        self._install_the_interpreter()
        self.audit_names([])
        self.test_asserts("self.assertTrue(True)")

    def test_asserts(self, assertion: str) -> None:
        self._write("tests/test_push.py", TEST_MODULE.format(assertion=assertion))

    def audit_names(self, works: list[dict]) -> None:
        self._write(str(AUDIT_SCRIPT), f"import json\n\nprint(json.dumps({{'works': {works!r}}}))\n")

    def add_unused_import(self) -> None:
        self._write("lib/unused.py", "import os\n")

    def push(self) -> subprocess.CompletedProcess:
        environment = {key: value for key, value in os.environ.items() if key not in REPOSITORY_LOCATING_VARIABLES}
        environment["HOME"] = str(self._home)
        return subprocess.run([str(self._root / PRE_PUSH), "origin", "unused"], cwd=self._root, input="",
                              capture_output=True, text=True, env=environment)

    def _install_the_hook(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self._root)], check=True)
        (self._root / PRE_PUSH).parent.mkdir(parents=True)
        shutil.copy(PROJECT_ROOT / PRE_PUSH, self._root / PRE_PUSH)

    def _install_the_interpreter(self) -> None:
        environment = self._home / VENV
        environment.parent.mkdir(parents=True)
        environment.symlink_to(sys.prefix, target_is_directory=True)

    def _write(self, relative: str, source: str) -> None:
        path = self._root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)


class TestThePrePushHookRunsTheFullChecks(unittest.TestCase):
    def setUp(self):
        scratch = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.tree = PushingTree(scratch / "tree", scratch / "home")

    def test_a_tree_that_passes_every_check_is_pushed(self):
        result = self.tree.push()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_one_failing_test_refuses_the_push(self):
        self.tree.test_asserts("self.assertEqual(1, 2)")
        result = self.tree.push()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("FAIL: test_push", result.stderr)
        self.assertIn("the test suite", result.stderr)

    def test_a_linter_finding_refuses_the_push(self):
        self.tree.add_unused_import()
        result = self.tree.push()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("F401", result.stdout)

    def test_a_named_work_refuses_the_push(self):
        self.tree.audit_names([NAMED_WORK])
        result = self.tree.push()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("lib/x.py:4: Doe - 2020 - A Work", result.stdout)


class TestTheRepositoryShipsTheHook(unittest.TestCase):
    def test_the_pre_push_hook_is_executable(self):
        self.assertTrue(os.access(PROJECT_ROOT / PRE_PUSH, os.X_OK))


if __name__ == "__main__":
    unittest.main()
