from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from _drive.script import REPOSITORY_ROOT
from _drive.work import STATE_ASIDE, WorkDirectory

STEP_RESULT_NAME = "step.json"
STEP_PID_NAME = "step.pid"
STEP_RESULT_PARTIAL_NAME = "step.json.part"
STATE_RUNNING = "running"
WAIT_SECONDS = 560
POLL_SECONDS = 5
RUN_COMMAND = "drive-run"


class DetachedLauncher:
    def __init__(self, script: Path, interpreter: str = sys.executable) -> None:
        self._script = script
        self._interpreter = interpreter

    def launch(self, *arguments: str | int) -> int:
        command = [self._interpreter, str(self._script), RUN_COMMAND, *(str(argument) for argument in arguments)]
        process = subprocess.Popen(command, cwd=REPOSITORY_ROOT, start_new_session=True, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return process.pid


class ProcessProbe:
    def is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class StepHost:
    def __init__(self, launcher: DetachedLauncher, probe: ProcessProbe | None = None,
                 clock: SystemClock | None = None) -> None:
        self.launcher = launcher
        self.probe = probe or ProcessProbe()
        self.clock = clock or SystemClock()


class DetachedStep:
    def __init__(self, work: WorkDirectory, host: StepHost) -> None:
        self._work = work
        self._launcher = host.launcher
        self._probe = host.probe
        self._clock = host.clock

    def start(self, *arguments: str | int) -> dict:
        if not self._is_running():
            self._work.path(STEP_RESULT_NAME).unlink(missing_ok=True)
            pid = self._launcher.launch(*arguments)
            self._work.write_text(STEP_PID_NAME, str(pid))
        return self._running()

    def record(self, outcome: dict) -> None:
        partial = self._work.path(STEP_RESULT_PARTIAL_NAME)
        partial.write_text(json.dumps(outcome, ensure_ascii=False))
        partial.replace(self._work.path(STEP_RESULT_NAME))

    def wait(self, timeout: float = WAIT_SECONDS) -> dict:
        deadline = self._clock.now() + timeout
        while self._result_pending() and self._clock.now() < deadline:
            self._clock.sleep(POLL_SECONDS)
        return self._settled()

    def _settled(self) -> dict:
        if self._work.has(STEP_RESULT_NAME):
            return self._collect()
        if self._is_running():
            return self._running()
        return self._died()

    def _collect(self) -> dict:
        self._work.path(STEP_PID_NAME).unlink(missing_ok=True)
        return self._work.load(STEP_RESULT_NAME)

    def _died(self) -> dict:
        self._clear()
        return self._work.outcome({"state": STATE_ASIDE, "question": "the driver step ended with no result"})

    def _clear(self) -> None:
        self._work.path(STEP_RESULT_NAME).unlink(missing_ok=True)
        self._work.path(STEP_PID_NAME).unlink(missing_ok=True)

    def _result_pending(self) -> bool:
        return not self._work.has(STEP_RESULT_NAME) and self._is_running()

    def _is_running(self) -> bool:
        return self._work.has(STEP_PID_NAME) and self._probe.is_alive(self._step_pid())

    def _step_pid(self) -> int:
        return int(self._work.path(STEP_PID_NAME).read_text().strip())

    def _running(self) -> dict:
        return self._work.outcome({"state": STATE_RUNNING})
