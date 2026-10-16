from __future__ import annotations

import os
from typing import TYPE_CHECKING

import psutil
from vault import ExtractionRecordsUnreadable, ReviewedSweep

from _drive.runlock import RunHolder, RunLock, RunLocked
from _drive.script import SkillScript
from _drive.work import SetAside

if TYPE_CHECKING:
    from _ingest.prefetchstep import DetachedPrefetch

SHELL_NAMES = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish", "tcsh", "csh"})
LOGIN_SHELL_MARK = "-"
STATE_RELEASED = "released"
STATE_NOT_HELD = "not-held"

__all__ = ["SHELL_NAMES", "STATE_NOT_HELD", "STATE_RELEASED", "RunEnd", "RunHolder", "RunLock", "RunLocked",
           "RunTeardown", "SessionProcess"]


class SessionProcess:
    @staticmethod
    def pid() -> int:
        return next((ancestor.pid for ancestor in psutil.Process().parents() if not SessionProcess._is_shell(ancestor)),
                    os.getppid())

    @staticmethod
    def _is_shell(process: psutil.Process) -> bool:
        return process.name().removeprefix(LOGIN_SHELL_MARK) in SHELL_NAMES


class RunEnd:
    def __init__(self, lock: RunLock, session: int, teardown: RunTeardown) -> None:
        self._lock = lock
        self._session = session
        self._teardown = teardown

    def finish(self) -> dict:
        if self._lock.held_by_another(self._session) is not None:
            return {"state": STATE_NOT_HELD}
        try:
            torn_down = self._teardown.run()
        finally:
            self._lock.release()
        return {"state": STATE_RELEASED, **torn_down}


class RunTeardown:
    def __init__(self, extract: SkillScript, sweep: ReviewedSweep, prefetch: DetachedPrefetch) -> None:
        self._extract = extract
        self._sweep = sweep
        self._prefetch = prefetch

    def run(self) -> dict:
        prefetch_stopped = self._prefetch.stop()
        return {"prefetch_stopped": prefetch_stopped, "stopped": self._stopped_servers(),
                "swept_bytes": self._swept_bytes()}

    def _stopped_servers(self) -> list[int]:
        run = self._extract.run("stop-servers")
        report = run.payload()
        if not isinstance(report, dict):
            raise SetAside(f"`extract.py stop-servers` failed, and the run lock was released: {run.tail}")
        return report.get("stopped", [])

    def _swept_bytes(self) -> int:
        try:
            return self._swept()
        except (OSError, ExtractionRecordsUnreadable) as failure:
            raise SetAside(f"the reviewed sweep failed, and the run lock was released: {failure}") from failure

    def _swept(self) -> int:
        caches = self._sweep.entries()
        swept_bytes = sum(cache.size() for cache in caches)
        self._sweep.delete(caches)
        return swept_bytes
