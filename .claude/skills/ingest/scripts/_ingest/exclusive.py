from __future__ import annotations

from pathlib import Path

from surya_servers import PidFile

from _drive.detached import STEP_PID_NAME, ProcessProbe
from _ingest.runlock import RunLock


class RunLockReadiness:
    def __init__(self, lock: RunLock, session: int) -> None:
        self._lock = lock
        self._session = session

    def failures(self) -> list[str]:
        holder = self._lock.held_by_another(self._session)
        return [] if holder is None else [holder.locked_question()]


class EngineRunReadiness:
    def __init__(self, path: Path, probe: ProcessProbe | None = None) -> None:
        self._path = path
        self._probe = probe or ProcessProbe()

    def failures(self) -> list[str]:
        if not self._path.exists():
            return []
        pid = PidFile(self._path).pid()
        if pid is not None and self._probe.is_alive(pid):
            return [f"an engine conversion runs: process {pid} holds {self._path}; wait until it finishes"]
        return [f"{self._path} names process {pid}, which is not running: a conversion stopped without clearing "
                f"the file; delete it, then start the run again"]


class DetachedStepsReadiness:
    def __init__(self, parents: list[Path], probe: ProcessProbe | None = None) -> None:
        self._parents = parents
        self._probe = probe or ProcessProbe()

    def failures(self) -> list[str]:
        return [f"a detached step still runs: process {pid} for {work.name}; wait until it finishes, or stop it"
                for work, pid in self._recorded_steps() if self._probe.is_alive(pid)]

    def _recorded_steps(self) -> list[tuple[Path, int]]:
        recorded = [(work, StepPid(work / STEP_PID_NAME).value()) for parent in self._parents if parent.is_dir()
                    for work in sorted(parent.iterdir())]
        return [(work, pid) for work, pid in recorded if pid is not None]


class StepPid:
    def __init__(self, path: Path) -> None:
        self._path = path

    def value(self) -> int | None:
        try:
            return int(self._path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
