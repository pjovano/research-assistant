from __future__ import annotations

import os
import signal
from collections.abc import Callable
from pathlib import Path

from _drive.detached import STEP_PID_NAME, ProcessProbe
from _ingest.exclusive import StepPid

PREFETCH_KEY = "prefetch"


class DetachedPrefetch:
    def __init__(self, step_dir: Path, probe: ProcessProbe | None = None,
                 signal_group: Callable[[int, int], None] = os.killpg) -> None:
        self._step_pid = StepPid(step_dir / STEP_PID_NAME)
        self._probe = probe or ProcessProbe()
        self._signal_group = signal_group

    def stop(self) -> int | None:
        pid = self._step_pid.value()
        if pid is None or not self._probe.is_alive(pid):
            return None
        self._signal_group(pid, signal.SIGTERM)
        return pid
