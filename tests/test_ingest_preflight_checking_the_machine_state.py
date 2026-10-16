from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _ingest.checkout import Checkout, CheckoutReadiness, WorkingDirectoryReadiness
from _ingest.exclusive import DetachedStepsReadiness, EngineRunReadiness, RunLockReadiness
from _ingest.preflight import Preflight
from _ingest.runlock import RunHolder, RunLock

STARTED_AT = 1_790_000_000.0
WORK = "Author - 2020 - Title"


def dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()
    return process.pid


class DirectoryCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)


class TestTheRunLockCheck(DirectoryCase):
    def check(self, holder: int) -> RunLockReadiness:
        lock = RunLock(self.directory / "ingest-run.json")
        lock.take(RunHolder(holder, "extract", STARTED_AT))
        return RunLockReadiness(lock, os.getpid())

    def test_a_lock_another_live_session_holds_is_a_failure_naming_it(self) -> None:
        failures = self.check(os.getppid()).failures()
        self.assertIn(f"process {os.getppid()}", failures[0])

    def test_a_lock_this_session_holds_passes(self) -> None:
        self.assertEqual([], self.check(os.getpid()).failures())

    def test_a_stale_lock_passes(self) -> None:
        self.assertEqual([], self.check(dead_pid()).failures())


class TestTheEngineRunCheck(DirectoryCase):
    def check(self, pid: int | None) -> list[str]:
        path = self.directory / "engine-run.json"
        if pid is not None:
            path.write_text(json.dumps({"pid": pid}), encoding="utf-8")
        return EngineRunReadiness(path).failures()

    def test_no_engine_run_file_passes(self) -> None:
        self.assertEqual([], self.check(None))

    def test_a_live_conversion_is_a_failure(self) -> None:
        self.assertIn("conversion runs", self.check(os.getpid())[0])

    def test_a_file_naming_a_dead_process_is_a_failure_that_says_so(self) -> None:
        self.assertIn("not running", self.check(dead_pid())[0])


class TestTheDetachedStepsCheck(DirectoryCase):
    def check(self, pid: int) -> list[str]:
        work = self.directory / "ingest" / WORK
        work.mkdir(parents=True)
        (work / "step.pid").write_text(str(pid), encoding="utf-8")
        return DetachedStepsReadiness([self.directory / "ingest", self.directory / "absent"]).failures()

    def test_a_live_detached_step_is_a_failure_naming_its_work(self) -> None:
        self.assertIn(WORK, self.check(os.getpid())[0])

    def test_a_dead_detached_step_passes(self) -> None:
        self.assertEqual([], self.check(dead_pid()))


class FakeCheckout(Checkout):
    def __init__(self, branch: str, changes: list[str]) -> None:
        super().__init__(Path("."))
        self._branch = branch
        self._changes = changes

    def branch(self) -> str:
        return self._branch

    def changes(self) -> list[str]:
        return self._changes


class TestTheCheckoutCheck(unittest.TestCase):
    def test_main_with_no_change_passes(self) -> None:
        self.assertEqual([], CheckoutReadiness(FakeCheckout("main", [])).failures())

    def test_another_branch_is_a_failure_naming_it(self) -> None:
        self.assertIn("claude/fix", CheckoutReadiness(FakeCheckout("claude/fix", [])).failures()[0])

    def test_an_uncommitted_change_is_a_failure_naming_it(self) -> None:
        self.assertIn("lib/vault.py", CheckoutReadiness(FakeCheckout("main", [" M lib/vault.py"])).failures()[0])

    def test_a_directory_git_cannot_read_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("git cannot read", CheckoutReadiness(Checkout(Path(directory))).failures()[0])


class TestACheckoutReadByGit(DirectoryCase):
    def setUp(self) -> None:
        super().setUp()
        self.git("init", "--quiet", "--initial-branch", "main")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.directory), *args], check=True, capture_output=True)

    def test_the_branch_is_read(self) -> None:
        self.assertEqual("main", Checkout(self.directory).branch())

    def test_an_untracked_file_is_a_change(self) -> None:
        (self.directory / "new.txt").write_text("x", encoding="utf-8")
        self.assertEqual(1, len(Checkout(self.directory).changes()))


class TestTheWorkingDirectoryCheck(unittest.TestCase):
    def test_a_directory_under_the_worktrees_is_a_failure(self) -> None:
        directory = Path("~/Developer/research-tools/.claude/worktrees/fix").expanduser()
        self.assertEqual(1, len(WorkingDirectoryReadiness(directory).failures()))

    def test_the_repository_root_passes(self) -> None:
        directory = Path("~/Developer/research-tools").expanduser()
        self.assertEqual([], WorkingDirectoryReadiness(directory).failures())


class FailingCheck:
    def __init__(self, failure: str) -> None:
        self._failure = failure

    def failures(self) -> list[str]:
        return [self._failure]


class TestTheQuestion(unittest.TestCase):
    def test_the_halt_names_every_failed_check(self) -> None:
        outcome = Preflight([FailingCheck("the run lock"), FailingCheck("the branch")]).outcome()
        self.assertEqual({"state": "halt", "question": "the run lock | the branch"}, outcome)


if __name__ == "__main__":
    unittest.main()
