from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

Device = Literal["mps", "cuda", "cpu"]


class Level(enum.Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    SERIOUS = "serious"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Job:
    label: str
    command: tuple[str, ...]
    interval_seconds: int | None = None
    keep_alive: bool = False
    working_directory: Path | None = None


class Notice(Protocol):
    @property
    def message(self) -> str: ...


class Scheduler(Protocol):
    def install(self, job: Job) -> None: ...

    def installed(self, job: Job) -> bool: ...

    def remove(self, job: Job) -> None: ...


class Notifier(Protocol):
    def notify(self, alert: Notice) -> None: ...


class SystemReadings(Protocol):
    def memory_pressure(self) -> Level: ...

    def thermal(self) -> Level: ...

    def swap_used(self) -> int: ...


class Accelerator(Protocol):
    def device(self) -> Device: ...

    def reachable(self) -> str | None: ...


class Trash(Protocol):
    def discard(self, path: Path) -> None: ...


class SyncedFolder(Protocol):
    def conflict_copies(self, directory: Path) -> list[Path]: ...

    def not_downloaded(self, path: Path) -> bool: ...


class Locations(Protocol):
    @property
    def vault_root(self) -> Path: ...

    @property
    def inbox(self) -> Path: ...

    @property
    def state_dir(self) -> Path: ...

    @property
    def rag_dir(self) -> Path: ...
