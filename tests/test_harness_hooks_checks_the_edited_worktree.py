import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import harness_hooks
from _hooks.work_tree import CheckedTree, without_repository_locating_variables

PRINTS_ITS_DIRECTORY_AND_FAILS = (sys.executable, "-c", "import os, sys; print(os.getcwd()); sys.exit(1)")
EDITED = Path("lib/edited.py")


class Checkout:
    def __init__(self, root: Path) -> None:
        self.root = root

    def edited(self) -> Path:
        path = self.root / EDITED
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("EDITED = 1\n")
        return path


class GitRepository(Checkout):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        root.mkdir()
        self._git("init", "--quiet")
        self._git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "--quiet",
                  "--allow-empty", "-m", "start")

    def worktree(self, path: Path) -> Checkout:
        self._git("worktree", "add", "--quiet", "--detach", str(path))
        return Checkout(path)

    def _git(self, *arguments: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *arguments], check=True, capture_output=True,
                       env=without_repository_locating_variables(os.environ))


class TestTheCheckedTreeHoldsTheEditedFile(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.repository = GitRepository(self.scratch / "main")
        self.worktree = self.repository.worktree(self.scratch / "linked")

    def test_an_edit_in_a_worktree_of_the_project_is_checked_in_that_worktree(self):
        self.assertEqual(self.worktree.root, CheckedTree(self.worktree.edited(), self.repository.root).root())

    def test_an_edit_in_a_worktree_nested_inside_the_project_is_checked_in_that_worktree(self):
        nested = self.repository.worktree(self.repository.root / ".claude/worktrees/nested")
        self.assertEqual(nested.root, CheckedTree(nested.edited(), self.repository.root).root())

    def test_an_edit_in_the_project_is_checked_in_the_project(self):
        edited = self.repository.edited()
        self.assertEqual(self.repository.root, CheckedTree(edited, self.repository.root).root())

    def test_an_edit_in_an_unrelated_repository_is_checked_nowhere(self):
        unrelated = GitRepository(self.scratch / "unrelated")
        self.assertIsNone(CheckedTree(unrelated.edited(), self.repository.root).root())


class TestTheHookRunsTheChecksInTheEditedWorktree(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.repository = GitRepository(self.scratch / "main")
        self.enterContext(mock.patch.object(harness_hooks.LintCheck, "COMMAND", PRINTS_ITS_DIRECTORY_AND_FAILS))

    def _report_after_editing(self, checkout: Checkout) -> tuple[int, str]:
        event = harness_hooks.HookEvent({"tool_input": {"file_path": str(checkout.edited())}})
        err = io.StringIO()
        with redirect_stderr(err):
            code = harness_hooks.HookCli(self.repository.root).run("checks-after-edit", event)
        return code, err.getvalue()

    def test_the_checks_run_from_the_root_of_the_worktree_that_holds_the_edit(self):
        worktree = self.repository.worktree(self.scratch / "linked")
        code, report = self._report_after_editing(worktree)
        self.assertEqual(harness_hooks.BLOCKING_EXIT_CODE, code)
        self.assertIn(f"\n{worktree.root}\n", report)

    def test_an_edit_in_an_unrelated_repository_runs_no_check(self):
        unrelated = GitRepository(self.scratch / "unrelated")
        self.assertEqual((0, ""), self._report_after_editing(unrelated))


if __name__ == "__main__":
    unittest.main()
