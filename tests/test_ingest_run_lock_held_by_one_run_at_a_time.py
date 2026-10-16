from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import psutil

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _drive.work import STATE_HALT, SetAside
from _ingest.prefetchstep import DetachedPrefetch
from _ingest.runlock import SHELL_NAMES, RunEnd, RunHolder, RunLock, RunLocked, RunTeardown, SessionProcess
from _ingest_home import INGEST, TemporaryHome
from _vault.reviewed import RECORDS_FILE_NAME, REVIEWED_KEY, ReviewedBasenames
from _vault.scratch import RENDER_NAME, RUN_LOCK_NAME, ReviewedSweep

STARTED_AT = 1_790_000_000.0
STOPPED = [111, 222]
REVIEWED = "Doe - 2020 - A Work"
RENDER_BYTES = b"0123456789"


def dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()
    return process.pid


class StopServersScript(SkillScript):
    def __init__(self, run: ScriptRun) -> None:
        super().__init__(Path("extract.py"))
        self._run = run
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self._run


class LockCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / RUN_LOCK_NAME
        self.lock = RunLock(self.path)
        self.records = Path(directory.name) / RECORDS_FILE_NAME
        self.records.write_text(json.dumps({REVIEWED: {REVIEWED_KEY: "2026-10-01"}}), encoding="utf-8")
        self.render = Path(directory.name) / REVIEWED / RENDER_NAME.format(number=1)
        self.render.parent.mkdir()
        self.render.write_bytes(RENDER_BYTES)

    def holder(self, pid: int) -> RunHolder:
        return RunHolder(pid, "extract", STARTED_AT)

    def recorded_pid(self) -> int:
        return json.loads(self.path.read_text(encoding="utf-8"))["pid"]


class TestTakingTheRunLock(LockCase):
    def test_a_free_lock_records_its_holder(self) -> None:
        self.lock.take(self.holder(os.getpid()))
        self.assertEqual(os.getpid(), self.recorded_pid())

    def test_a_lock_another_live_process_holds_halts_the_run(self) -> None:
        self.lock.take(self.holder(os.getppid()))
        with self.assertRaises(RunLocked) as raised:
            self.lock.take(self.holder(os.getpid()))
        self.assertEqual(STATE_HALT, raised.exception.fields["state"])

    def test_the_halt_names_the_holder(self) -> None:
        self.lock.take(self.holder(os.getppid()))
        with self.assertRaises(RunLocked) as raised:
            self.lock.take(self.holder(os.getpid()))
        self.assertIn(f"process {os.getppid()}", raised.exception.fields["question"])

    def test_a_lock_whose_holder_is_dead_is_stale_and_taken_over(self) -> None:
        self.lock.take(self.holder(dead_pid()))
        self.lock.take(self.holder(os.getpid()))
        self.assertEqual(os.getpid(), self.recorded_pid())

    def test_the_holding_session_takes_its_own_lock_again(self) -> None:
        self.lock.take(self.holder(os.getpid()))
        self.lock.take(self.holder(os.getpid()))
        self.assertEqual(os.getpid(), self.recorded_pid())

    def test_an_unreadable_lock_is_stale(self) -> None:
        self.path.write_text("{", encoding="utf-8")
        self.lock.take(self.holder(os.getpid()))
        self.assertEqual(os.getpid(), self.recorded_pid())


class TestEndingTheRun(LockCase):
    def run_end(self, run: ScriptRun) -> tuple[RunEnd, StopServersScript]:
        script = StopServersScript(run)
        sweep = ReviewedSweep(self.path.parent, ReviewedBasenames(self.records))
        prefetch = DetachedPrefetch(self.path.parent / "prefetch")
        return RunEnd(self.lock, os.getpid(), RunTeardown(script, sweep, prefetch)), script

    def test_the_holder_stops_the_servers_sweeps_the_reviewed_works_and_releases_the_lock(self) -> None:
        self.lock.take(self.holder(os.getpid()))
        run_end, _ = self.run_end(ScriptRun(0, json.dumps({"stopped": STOPPED})))
        self.assertEqual({"state": "released", "prefetch_stopped": None, "stopped": STOPPED,
                          "swept_bytes": len(RENDER_BYTES)},
                         run_end.finish())
        self.assertFalse(self.path.exists())

    def test_the_holder_deletes_the_renders_of_a_reviewed_work(self) -> None:
        self.lock.take(self.holder(os.getpid()))
        run_end, _ = self.run_end(ScriptRun(0, json.dumps({"stopped": STOPPED})))
        run_end.finish()
        self.assertFalse(self.render.exists())

    def test_a_failed_reviewed_sweep_sets_aside_and_still_releases_the_lock(self) -> None:
        self.lock.take(self.holder(os.getpid()))
        self.records.write_text("{", encoding="utf-8")
        run_end, _ = self.run_end(ScriptRun(0, json.dumps({"stopped": STOPPED})))
        with self.assertRaises(SetAside):
            run_end.finish()
        self.assertFalse(self.path.exists())

    def test_another_sessions_lock_is_kept_and_its_servers_left_up(self) -> None:
        self.lock.take(self.holder(os.getppid()))
        run_end, script = self.run_end(ScriptRun(0, json.dumps({"stopped": STOPPED})))
        self.assertEqual({"state": "not-held"}, run_end.finish())
        self.assertEqual([], script.calls)
        self.assertTrue(self.path.exists())
        self.assertTrue(self.render.exists())

    def test_a_failed_stop_servers_still_releases_the_lock(self) -> None:
        self.lock.take(self.holder(os.getpid()))
        run_end, _ = self.run_end(ScriptRun(1, "", "Traceback"))
        with self.assertRaises(SetAside):
            run_end.finish()
        self.assertFalse(self.path.exists())


class TestTheSessionProcess(unittest.TestCase):
    def test_the_holder_is_the_nearest_ancestor_that_is_not_a_shell(self) -> None:
        pid = SessionProcess.pid()
        self.assertNotIn(psutil.Process(pid).name().removeprefix("-"), SHELL_NAMES)
        self.assertIn(pid, [ancestor.pid for ancestor in psutil.Process().parents()])


class TestDriveBatchUnderAHeldLock(unittest.TestCase):
    def setUp(self) -> None:
        base = tempfile.TemporaryDirectory()
        self.addCleanup(base.cleanup)
        self.home = TemporaryHome(Path(base.name)).build().with_queued_work()
        RunLock(self.home.scratch / RUN_LOCK_NAME).take(RunHolder(os.getppid(), "extract", STARTED_AT))

    def test_drive_batch_halts_naming_the_holder(self) -> None:
        listed = self.home.last_line(INGEST, "drive-batch", "--from", "extract")
        self.assertEqual(STATE_HALT, listed["state"])
        self.assertIn(f"process {os.getppid()}", listed["question"])

    def test_preflight_halts_naming_the_holder(self) -> None:
        checked = self.home.last_line(INGEST, "preflight", "--from", "extract")
        self.assertIn(f"process {os.getppid()}", checked["question"])

    def test_drive_release_leaves_the_lock_to_its_holder(self) -> None:
        self.assertEqual("not-held", self.home.last_line(INGEST, "drive-release")["state"])


if __name__ == "__main__":
    unittest.main()
