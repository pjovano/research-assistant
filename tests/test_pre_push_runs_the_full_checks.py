import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, LiveTree

LiveTree.activate()

from _hooks.work_tree import without_repository_locating_variables

PRE_PUSH = Path(".githooks/pre-push")
HOOK_SCRIPT = Path("lib/harness_hooks.py")
LINTER_CONFIGURATION = Path("pyproject.toml")
AUDIT_SCRIPT = Path(".claude/skills/vault-audit/scripts/audit.py")
VENV = Path(".research-vault/venv")
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
        environment = without_repository_locating_variables(os.environ)
        environment["HOME"] = str(self._home)
        return subprocess.run([str(self._root / PRE_PUSH), "origin", "unused"], cwd=self._root, input="",
                              capture_output=True, text=True, env=environment)

    def _install_the_hook(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self._root)], check=True)
        (self._root / PRE_PUSH).parent.mkdir(parents=True)
        shutil.copy(PROJECT_ROOT / PRE_PUSH, self._root / PRE_PUSH)
        shutil.copy(PROJECT_ROOT / LINTER_CONFIGURATION, self._root / LINTER_CONFIGURATION)
        self._install_the_hook_script()

    def _install_the_hook_script(self) -> None:
        library = self._root / HOOK_SCRIPT.parent
        library.mkdir(parents=True)
        shutil.copy(PROJECT_ROOT / HOOK_SCRIPT, self._root / HOOK_SCRIPT)
        for package in (PROJECT_ROOT / HOOK_SCRIPT.parent).glob("_*"):
            (library / package.name).symlink_to(package, target_is_directory=True)

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
        self.assertIn("the test suite fails", result.stderr)

    def test_a_linter_finding_refuses_the_push(self):
        self.tree.add_unused_import()
        result = self.tree.push()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("F401", result.stderr)

    def test_a_named_work_refuses_the_push(self):
        self.tree.audit_names([NAMED_WORK])
        result = self.tree.push()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("lib/x.py:4: Doe - 2020 - A Work", result.stderr)


class TestTheRepositoryShipsTheHook(unittest.TestCase):
    def test_the_pre_push_hook_is_executable(self):
        self.assertTrue(os.access(PROJECT_ROOT / PRE_PUSH, os.X_OK))


if __name__ == "__main__":
    unittest.main()
