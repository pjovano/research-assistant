from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import psutil

from _support import LiveTree

LiveTree.activate()

from _drive.detached import STEP_PID_NAME
from _ingest.prefetchstep import DetachedPrefetch

EXIT_WAIT_SECONDS = 10
POLL_SECONDS = 0.05
PREFETCH_WITH_A_CHILD = ("import subprocess, sys; "
                         "subprocess.run([sys.executable, '-c', 'import time; time.sleep(60)'])")


class TestStoppingTheRunsPrefetch(unittest.TestCase):
    def setUp(self) -> None:
        self.step_dir = Path(self.enterContext(tempfile.TemporaryDirectory())) / "prefetch"
        self.step_dir.mkdir()

    def started_prefetch(self) -> subprocess.Popen:
        step = subprocess.Popen([sys.executable, "-c", PREFETCH_WITH_A_CHILD], start_new_session=True)
        self.addCleanup(self._reap, step)
        (self.step_dir / STEP_PID_NAME).write_text(str(step.pid))
        return step

    @staticmethod
    def _reap(step: subprocess.Popen) -> None:
        if step.poll() is None:
            parent = psutil.Process(step.pid)
            for process in [*parent.children(recursive=True), parent]:
                process.kill()
        step.wait(EXIT_WAIT_SECONDS)

    @staticmethod
    def children_of(step: subprocess.Popen) -> list[psutil.Process]:
        parent = psutil.Process(step.pid)
        deadline = time.monotonic() + EXIT_WAIT_SECONDS
        while not parent.children() and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        return parent.children()

    def test_the_step_and_the_conversion_it_started_are_stopped(self) -> None:
        step = self.started_prefetch()
        children = self.children_of(step)
        DetachedPrefetch(self.step_dir).stop()
        step.wait(EXIT_WAIT_SECONDS)
        _, alive = psutil.wait_procs(children, timeout=EXIT_WAIT_SECONDS)
        self.assertEqual([], alive)

    def test_the_stopped_step_is_named(self) -> None:
        step = self.started_prefetch()
        self.assertEqual(step.pid, DetachedPrefetch(self.step_dir).stop())

    def test_a_run_that_started_no_prefetch_stops_nothing(self) -> None:
        self.assertIsNone(DetachedPrefetch(self.step_dir).stop())

    def test_a_prefetch_that_already_ended_is_not_signalled(self) -> None:
        signalled = []
        (self.step_dir / STEP_PID_NAME).write_text(str(self._ended_pid()))
        DetachedPrefetch(self.step_dir, signal_group=lambda pid, number: signalled.append(pid)).stop()
        self.assertEqual([], signalled)

    @staticmethod
    def _ended_pid() -> int:
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait(EXIT_WAIT_SECONDS)
        return ended.pid


if __name__ == "__main__":
    unittest.main()
