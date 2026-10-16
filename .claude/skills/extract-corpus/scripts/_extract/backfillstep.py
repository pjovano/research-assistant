from __future__ import annotations

import sys

from _drive.detached import (
    POLL_SECONDS,
    RUN_COMMAND,
    STATE_RUNNING,
    STEP_PID_NAME,
    STEP_RESULT_NAME,
    STEP_RESULT_PARTIAL_NAME,
    WAIT_SECONDS,
    DetachedLauncher,
    DetachedStep,
    ProcessProbe,
    StepHost,
    SystemClock,
)
from _extract.backfillrunner import EXTRACT_SCRIPT

__all__ = [
    "POLL_SECONDS", "RUN_COMMAND", "STATE_RUNNING", "STEP_PID_NAME", "STEP_RESULT_NAME", "STEP_RESULT_PARTIAL_NAME",
    "WAIT_SECONDS", "DetachedStep", "ProcessProbe", "StepHost", "StepLauncher", "SystemClock",
]


class StepLauncher(DetachedLauncher):
    def __init__(self, interpreter: str = sys.executable) -> None:
        super().__init__(EXTRACT_SCRIPT, interpreter)
