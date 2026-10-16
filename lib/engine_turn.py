from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path
from typing import IO

import vault

TURN_NAME = "engine-turn.lock"
WAITING_NAME = "engine-waiting"
YIELD_POLL_SECONDS = 5.0


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TurnClock:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class EngineTurn:
    def __init__(self, path: Path | None = None, waiting_dir: Path | None = None) -> None:
        self._path = path or vault.SCRATCH_DIR / TURN_NAME
        self._waiting_dir = waiting_dir or vault.SCRATCH_DIR / WAITING_NAME
        self._handle: IO | None = None

    def take(self) -> None:
        marker = self._waiting_dir / str(os.getpid())
        self._waiting_dir.mkdir(parents=True, exist_ok=True)
        marker.touch()
        try:
            self._lock(fcntl.LOCK_EX)
        finally:
            marker.unlink(missing_ok=True)

    def give_back(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle, fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def is_wanted_by_another(self) -> bool:
        if not self._waiting_dir.is_dir():
            return False
        pids = (int(marker.name) for marker in self._waiting_dir.iterdir() if marker.name.isdigit())
        return any(pid != os.getpid() and process_is_alive(pid) for pid in pids)

    def try_take(self) -> bool:
        try:
            self._lock(fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _lock(self, operation: int) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a")
        try:
            fcntl.flock(handle, operation)
        except BaseException:
            handle.close()
            raise
        self._handle = handle


class YieldingEngineTurn(EngineTurn):
    def __init__(self, path: Path | None = None, waiting_dir: Path | None = None, clock: TurnClock | None = None,
                 poll_seconds: float = YIELD_POLL_SECONDS) -> None:
        super().__init__(path, waiting_dir)
        self._clock = clock or TurnClock()
        self._poll_seconds = poll_seconds

    def take(self) -> None:
        while self.is_wanted_by_another() or not self.try_take():
            self._clock.sleep(self._poll_seconds)
