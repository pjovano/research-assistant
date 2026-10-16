from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import vault
from _vault.scratch import RUN_LOCK_NAME

from _drive.detached import ProcessProbe
from _drive.work import Halt


@dataclass(frozen=True)
class RunHolder:
    pid: int
    origin: str
    started_at: float

    def describe(self) -> str:
        stamp = datetime.fromtimestamp(self.started_at, timezone.utc).astimezone().isoformat(timespec="minutes")
        return f"process {self.pid}, a run from {self.origin} started {stamp}"

    def locked_question(self) -> str:
        return (f"another ingest run holds the run lock: {self.describe()}; wait until that run returns, or stop the "
                f"session that runs it, then start this run again")


class RunLocked(Halt):
    def __init__(self, holder: RunHolder) -> None:
        super().__init__(holder.locked_question())


class RunLock:
    def __init__(self, path: Path, probe: ProcessProbe | None = None) -> None:
        self._path = path
        self._probe = probe or ProcessProbe()

    @classmethod
    def ingest(cls) -> RunLock:
        return cls(vault.SCRATCH_DIR / RUN_LOCK_NAME)

    def holder(self) -> RunHolder | None:
        recorded = self._recorded()
        return recorded if recorded is not None and self._probe.is_alive(recorded.pid) else None

    def held_by_another(self, pid: int) -> RunHolder | None:
        holder = self.holder()
        return holder if holder is not None and holder.pid != pid else None

    def is_held_by(self, pid: int | None) -> bool:
        holder = self.holder()
        return holder is not None and holder.pid == pid

    def take(self, holder: RunHolder) -> None:
        try:
            self._create(holder)
        except FileExistsError:
            self._replace(holder)

    def release(self) -> None:
        self._path.unlink(missing_ok=True)

    def _create(self, holder: RunHolder) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("x", encoding="utf-8") as lock:
            json.dump(asdict(holder), lock)

    def _replace(self, holder: RunHolder) -> None:
        other = self.held_by_another(holder.pid)
        if other is not None:
            raise RunLocked(other)
        self._path.write_text(json.dumps(asdict(holder)), encoding="utf-8")

    def _recorded(self) -> RunHolder | None:
        try:
            return RunHolder(**json.loads(self._path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None
